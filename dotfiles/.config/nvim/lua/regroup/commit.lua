local M = {}

local diff = require('regroup.diff')

local function notify(msg, level)
  vim.notify(msg, level or vim.log.levels.INFO)
end

function M.refresh_signs()
  local gs = package.loaded.gitsigns
  if gs then pcall(gs.reset_base, true) end
end

-- Scratch commit buffer: `seed` is the editable message, `comments` the '#'-prefixed
-- context listing what is being committed. Comment lines are stripped before `on_write`
-- receives the message; an error thrown there keeps the buffer open to retry.
function M.buffer(seed, comments, on_write)
  local existing = vim.fn.bufnr('regroup://commit')
  if existing ~= -1 then vim.api.nvim_buf_delete(existing, { force = true }) end
  local buf = vim.api.nvim_create_buf(false, false)
  vim.api.nvim_buf_set_name(buf, 'regroup://commit')

  local lines = vim.list_extend({}, seed)
  table.insert(lines, '')
  table.insert(lines, '# Write (:w) to commit, quit to abort.')
  vim.list_extend(lines, comments)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)

  vim.bo[buf].buftype = 'acwrite'
  vim.bo[buf].bufhidden = 'wipe'
  vim.bo[buf].filetype = 'gitcommit'
  vim.bo[buf].modified = false

  vim.api.nvim_create_autocmd('BufWriteCmd', {
    buffer = buf,
    callback = function()
      local msg = {}
      for _, l in ipairs(vim.api.nvim_buf_get_lines(buf, 0, -1, false)) do
        if not l:match('^#') then table.insert(msg, l) end
      end
      while #msg > 0 and msg[#msg] == '' do table.remove(msg) end
      if #msg == 0 then
        return notify('empty commit message', vim.log.levels.ERROR)
      end
      local ok, err = pcall(on_write, table.concat(msg, '\n') .. '\n')
      if ok then
        vim.bo[buf].modified = false
        vim.api.nvim_buf_delete(buf, { force = true })
      else
        notify(err, vim.log.levels.ERROR)
      end
    end,
  })

  vim.cmd('botright split')
  vim.api.nvim_win_set_buf(0, buf)
  vim.api.nvim_win_set_height(0, math.min(#lines + 2, 15))
end

-- commits whatever the index holds; returns the short hash
function M.run(root, msg)
  local res = diff.git(root, { 'commit', '-F', '-' }, { stdin = msg })
  assert(res.code == 0, 'git commit failed:\n' .. (res.stderr or '') .. (res.stdout or ''))
  M.refresh_signs()
  return vim.trim(diff.git(root, { 'rev-parse', '--short', 'HEAD' }).stdout)
end

-- commit the staged files, message written in the shared commit buffer
function M.index(root)
  root = root or diff.root()
  local res = diff.git(root, { 'diff', '--cached', '--name-status' })
  assert(res.code == 0, 'git diff --cached failed:\n' .. (res.stderr or ''))
  local staged = {}
  for _, l in ipairs(vim.split(vim.trim(res.stdout), '\n', { plain = true })) do
    if l ~= '' then table.insert(staged, '#   ' .. l:gsub('\t', '  ')) end
  end
  if #staged == 0 then
    return notify('nothing staged', vim.log.levels.ERROR)
  end

  M.buffer({ '' }, staged, function(msg)
    local short = M.run(root, msg)
    notify(('✓ %s %s'):format(short, msg:match('^[^\n]*')))
  end)
end

return M
