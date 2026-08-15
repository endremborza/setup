local M = {}

local diff = require('regroup.diff')

M.PREFIX = 'regroup: '

function M.list(root)
  local res = diff.git(root, { 'stash', 'list', '--format=%gd%x09%cr%x09%gs' })
  assert(res.code == 0, 'git stash list failed:\n' .. (res.stderr or ''))
  local out = {}
  for _, line in ipairs(vim.split(res.stdout or '', '\n', { plain = true, trimempty = true })) do
    local gd, age, gs = line:match('^(.-)\t(.-)\t(.*)$')
    local title = gs and gs:match(vim.pesc(M.PREFIX) .. '(.*)$')
    if title then
      table.insert(out, { gd = gd, age = age, gs = gs, title = title })
    end
  end
  return out
end

local function resolve(root, entry)
  for _, e in ipairs(M.list(root)) do
    if e.gs == entry.gs then return e.gd end
  end
  error('graveyard entry no longer exists: ' .. entry.title, 0)
end

function M.bury(root, title)
  local res = diff.git(root, { 'stash', 'push', '--staged', '-m', M.PREFIX .. title })
  assert(res.code == 0, 'git stash push --staged failed:\n' .. (res.stderr or '') .. (res.stdout or ''))
end

function M.pop(root, entry)
  local res = diff.git(root, { 'stash', 'pop', resolve(root, entry) })
  assert(res.code == 0, 'git stash pop failed (entry kept):\n' .. (res.stderr or '') .. (res.stdout or ''))
end

function M.drop(root, entry)
  local res = diff.git(root, { 'stash', 'drop', resolve(root, entry) })
  assert(res.code == 0, 'git stash drop failed:\n' .. (res.stderr or ''))
end

function M.show(root, entry)
  local res = diff.git(root, { 'stash', 'show', '-p', resolve(root, entry) })
  return res.code == 0 and res.stdout or (res.stderr or '')
end

return M
