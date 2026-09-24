local M = {}

function M.root()
  local res = vim.system({ 'git', 'rev-parse', '--show-toplevel' }, { text = true }):wait()
  assert(res.code == 0, 'not in a git repository')
  return vim.trim(res.stdout)
end

-- the repo root, or nil after telling the user why
function M.try_root()
  local ok, root = pcall(M.root)
  if ok then return root end
  vim.notify(root, vim.log.levels.ERROR)
  return nil
end

-- read-only git: the engine owns every write
function M.git(root, args, opts)
  local cmd = { 'git', '-C', root }
  vim.list_extend(cmd, args)
  return vim.system(cmd, vim.tbl_extend('force', { text = true }, opts or {})):wait()
end

local function output(res)
  return vim.trim((res.stderr or '') .. (res.stdout or ''))
end

-- The engine owns the diff, the cache and every git write; nvim only shows its output.
function M.engine(root, args, on_done)
  local cmd = { 'dienpy', 'hunks' }
  vim.list_extend(cmd, args)
  if on_done then
    return vim.system(cmd, { text = true, cwd = root }, vim.schedule_wrap(on_done))
  end
  return vim.system(cmd, { text = true, cwd = root }):wait()
end

function M.engine_ok(root, args)
  local res = M.engine(root, args)
  assert(res.code == 0, output(res))
  return res.stdout
end

M.output = output

return M
