local M = {}

local GIT_CFG = { '-c', 'diff.noprefix=false', '-c', 'diff.mnemonicprefix=false', '-c', 'core.quotePath=false' }

local function sys(cmd, opts)
  return vim.system(cmd, vim.tbl_extend('force', { text = true }, opts or {})):wait()
end

local function git(root, args, opts)
  local cmd = { 'git' }
  vim.list_extend(cmd, GIT_CFG)
  vim.list_extend(cmd, args)
  return sys(cmd, vim.tbl_extend('force', { cwd = root }, opts or {}))
end

function M.root()
  local res = sys({ 'git', 'rev-parse', '--show-toplevel' })
  assert(res.code == 0, 'not in a git repository')
  return vim.trim(res.stdout)
end

local function file_path(header)
  for _, l in ipairs(header) do
    local p = l:match('^%+%+%+ b/(.+)$')
    if p then return p end
  end
  for _, l in ipairs(header) do
    local p = l:match('^%-%-%- a/(.+)$')
    if p then return p end
  end
  return header[1]:match(' b/(.+)$')
end

function M.parse_diff(text)
  local files = {}
  local lines = vim.split(text, '\n', { plain = true })
  local i = 1
  local cur
  while i <= #lines do
    local line = lines[i]
    if line:match('^diff %-%-git ') then
      cur = { header = { line }, hunks = {} }
      table.insert(files, cur)
      i = i + 1
      while i <= #lines and not lines[i]:match('^@@ ') and not lines[i]:match('^diff %-%-git ') do
        table.insert(cur.header, lines[i])
        i = i + 1
      end
      cur.path = file_path(cur.header)
    elseif cur and line:match('^@@ ') then
      local hunk = {
        header = line,
        new_start = tonumber(line:match('%+(%d+)')) or 1,
        lines = {},
      }
      table.insert(cur.hunks, hunk)
      i = i + 1
      while i <= #lines do
        local c = lines[i]:sub(1, 1)
        if c == ' ' or c == '+' or c == '-' or c == '\\' then
          table.insert(hunk.lines, lines[i])
          i = i + 1
        else
          break
        end
      end
    else
      i = i + 1
    end
  end
  return files
end

function M.parse(root, opts)
  opts = opts or {}
  local res = git(root, { 'diff', '--no-ext-diff', '--no-color', opts.cached and '--cached' or 'HEAD' })
  assert(res.code == 0, 'git diff failed: ' .. (res.stderr or ''))
  local files = M.parse_diff(res.stdout)

  if not opts.cached then
    local ls = git(root, { 'ls-files', '--others', '--exclude-standard' })
    for _, f in ipairs(vim.split(ls.stdout or '', '\n', { plain = true, trimempty = true })) do
      local d = git(root, { 'diff', '--no-color', '--no-index', '--', '/dev/null', f })
      local uf = M.parse_diff(d.stdout)[1]
      if uf then
        uf.path = f
        uf.untracked = true
        table.insert(files, uf)
      end
    end
  end

  local hunks, by_id, counts = {}, {}, {}
  local function register(rec, body)
    local base = vim.fn.sha256(rec.path .. '\031' .. table.concat(body, '\n')):sub(1, 12)
    local n = (counts[base] or 0) + 1
    counts[base] = n
    rec.id = n == 1 and base or (base .. '~' .. n)
    table.insert(hunks, rec)
    by_id[rec.id] = rec
  end

  for fi, f in ipairs(files) do
    assert(f.path, 'could not determine path for diff section: ' .. f.header[1])
    if #f.hunks == 0 then
      local body = vim.tbl_filter(function(l) return not l:match('^index ') end, f.header)
      register({ path = f.path, kind = f.untracked and 'untracked' or 'file', file = f, fi = fi, hi = 0, new_start = 1 }, body)
    else
      for hi, h in ipairs(f.hunks) do
        register({
          path = f.path,
          kind = f.untracked and 'untracked' or 'hunk',
          file = f,
          hunk = h,
          fi = fi,
          hi = hi,
          new_start = math.max(1, h.new_start),
        }, h.lines)
      end
    end
  end

  return { root = root, files = files, hunks = hunks, by_id = by_id }
end

function M.hunk_text(rec)
  if rec.hunk then
    return rec.hunk.header .. '\n' .. table.concat(rec.hunk.lines, '\n')
  end
  return table.concat(rec.file.header, '\n')
end

local function rename_source(rec)
  for _, l in ipairs(rec.file.header) do
    local p = l:match('^rename from (.+)$')
    if p then return p end
  end
end

local function split_actions(parse, ids)
  local sel = {}
  for _, id in ipairs(ids) do
    assert(parse.by_id[id], 'unknown hunk id: ' .. id)
    sel[id] = true
  end
  local patch, adds, seen_file, seen_add = {}, {}, {}, {}
  local function add_path(p)
    if p and not seen_add[p] then
      seen_add[p] = true
      table.insert(adds, p)
    end
  end
  for _, rec in ipairs(parse.hunks) do
    if sel[rec.id] then
      if rec.kind == 'hunk' then
        if not seen_file[rec.file] then
          seen_file[rec.file] = true
          vim.list_extend(patch, rec.file.header)
        end
        table.insert(patch, rec.hunk.header)
        vim.list_extend(patch, rec.hunk.lines)
      else
        add_path(rec.path)
        add_path(rename_source(rec))
      end
    end
  end
  return #patch > 0 and (table.concat(patch, '\n') .. '\n') or nil, adds
end

function M.stage(parse, ids)
  local patch, adds = split_actions(parse, ids)
  if patch then
    local res = git(parse.root, { 'apply', '--cached', '--whitespace=nowarn', '-' }, { stdin = patch })
    assert(res.code == 0, 'git apply failed:\n' .. (res.stderr or ''))
  end
  if #adds > 0 then
    local res = git(parse.root, vim.list_extend({ 'add', '--' }, adds))
    assert(res.code == 0, 'git add failed:\n' .. (res.stderr or ''))
  end
end

function M.unstage(parse, ids)
  local patch, adds = split_actions(parse, ids)
  if patch then
    local res = git(parse.root, { 'apply', '--cached', '--reverse', '--whitespace=nowarn', '-' }, { stdin = patch })
    assert(res.code == 0, 'git apply --reverse failed:\n' .. (res.stderr or ''))
  end
  if #adds > 0 then
    local res = git(parse.root, vim.list_extend({ 'restore', '--staged', '--' }, adds))
    assert(res.code == 0, 'git restore --staged failed:\n' .. (res.stderr or ''))
  end
end

return M
