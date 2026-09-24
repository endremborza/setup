local picker = require('regroup.picker')

local M = {}

M.base = 'HEAD'

local left, right, status

function M.active()
  return left ~= nil and right ~= nil
      and vim.api.nvim_win_is_valid(left)
      and vim.api.nvim_win_is_valid(right)
end

local function in_base(file)
  if file == '' then return false end
  local res = vim.system({ 'git', '-C', vim.fs.dirname(file), 'rev-parse', '--show-toplevel' }, { text = true }):wait()
  if res.code ~= 0 then return false end
  local root = vim.trim(res.stdout)
  local rel = file:sub(#root + 2)
  return vim.system({ 'git', '-C', root, 'cat-file', '-e', M.base .. ':' .. rel }):wait().code == 0
end

local function split_current()
  -- no M.base version (untracked/new file) -> plain buffer, no diff split
  if not in_base(vim.api.nvim_buf_get_name(0)) then
    left, right = nil, nil
    return
  end
  local before = {}
  for _, w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do before[w] = true end
  local file_win = vim.api.nvim_get_current_win()
  vim.cmd('Gvdiffsplit ' .. M.base)
  local new_win
  for _, w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    if not before[w] then
      new_win = w; break
    end
  end
  left = new_win or vim.api.nvim_get_current_win()
  right = file_win
  vim.api.nvim_set_current_win(right)
  vim.schedule(function() vim.cmd('diffupdate!') end)
end

local function refile(file)
  if vim.api.nvim_win_is_valid(left) then
    vim.api.nvim_win_close(left, false)
  end
  vim.api.nvim_set_current_win(right)
  vim.cmd('diffoff')
  vim.cmd('edit ' .. vim.fn.fnameescape(file))
  split_current()
end

-- closes only the windows review mode opened: the base side and the status pane
function M.close()
  for _, w in ipairs({ left, status }) do
    if w and vim.api.nvim_win_is_valid(w) then vim.api.nvim_win_close(w, false) end
  end
  if right and vim.api.nvim_win_is_valid(right) then
    vim.api.nvim_set_current_win(right)
    vim.cmd('diffoff')
  end
  left, right, status = nil, nil, nil
end

function M.toggle()
  if M.active() then
    M.close()
    return
  end
  vim.cmd('botright Git')
  status = vim.api.nvim_get_current_win()
  vim.cmd('resize 15')
  vim.cmd('normal! G')
  vim.cmd('wincmd k')
  split_current()
end

function M.open(file)
  if not M.active() then
    vim.cmd('edit ' .. vim.fn.fnameescape(file))
    return
  end
  refile(file)
end

function M.jump(file, line)
  if M.active() then
    if vim.api.nvim_buf_get_name(vim.api.nvim_win_get_buf(right)) ~= file then
      refile(file)
    else
      vim.api.nvim_set_current_win(right)
    end
  else
    vim.cmd('edit ' .. vim.fn.fnameescape(file))
    split_current()
  end
  pcall(vim.api.nvim_win_set_cursor, 0, { line, 0 })
  vim.cmd('normal! zvzz')
end

-- Changed files (against the index in HEAD mode, against M.base otherwise): <CR> opens
-- one in the review diff, <Right>/<Left> stage and unstage it, <C-y> commits the index.
function M.pick_file()
  local tele = require('telescope.builtin')
  local action_state = require('telescope.actions.state')
  local function attach(prompt_bufnr, map)
    local t = picker.tools(prompt_bufnr, map, function()
      local finders = require('telescope.finders')
      local p = action_state.get_current_picker(prompt_bufnr)
      local fopts = { cwd = p.cwd, split_char = '\0' }
      fopts.entry_maker = require('telescope.make_entry').gen_from_git_status(fopts)
      return finders.new_oneshot_job({ 'git', 'status', '-z', '-uall', '--', '.' }, fopts)
    end)
    local function cwd() return action_state.get_current_picker(prompt_bufnr).cwd end
    local function stage(add)
      local entry = action_state.get_selected_entry()
      if not entry then return end
      vim.system(add and { 'git', 'add', '--', entry.value }
        or { 'git', 'restore', '--staged', '--', entry.value }, { cwd = cwd() }):wait()
      if M.base == 'HEAD' then t.refresh() end
    end
    t.bind('<CR>', 'open in the review diff', function()
      local entry = action_state.get_selected_entry()
      if not entry then return end
      t.close()
      M.open(entry.path)
    end)
    t.bind('<Right>', 'stage file', function() stage(true) end)
    t.bind('<Left>', 'unstage file', function() stage(false) end)
    t.bind('<C-y>', 'commit the index', function()
      local root = cwd()
      t.close()
      require('regroup.commit').index(root)
    end)
    return true
  end
  if M.base == 'HEAD' then
    tele.git_status(picker.layout { attach_mappings = attach })
  else
    tele.git_files(picker.layout {
      git_command = { 'git', 'diff', '--name-only', M.base }, attach_mappings = attach,
    })
  end
end

-- the branch the review diffs against; <C-h> goes back to HEAD
function M.pick_base()
  require('telescope.builtin').git_branches(picker.layout {
    attach_mappings = function(prompt_bufnr, map)
      local t = picker.tools(prompt_bufnr, map)
      t.bind('<CR>', 'review against this branch', function()
        local branch = t.selected()
        if not branch then return end
        t.close()
        M.base = branch
      end)
      t.bind('<C-h>', 'review against HEAD', function()
        t.close()
        M.base = 'HEAD'
      end)
      return true
    end,
  })
end

return M
