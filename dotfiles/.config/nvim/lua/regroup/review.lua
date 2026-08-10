local M = {}

M.base = 'HEAD'

local left, right

function M.active()
  return left ~= nil and right ~= nil
      and vim.api.nvim_win_is_valid(left)
      and vim.api.nvim_win_is_valid(right)
end

local function split_current()
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

function M.close()
  vim.api.nvim_set_current_win(right)
  vim.cmd('only')
  vim.cmd('diffoff')
  left, right = nil, nil
end

function M.toggle()
  if M.active() then
    M.close()
    return
  end
  vim.cmd('botright Git')
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

return M
