local M = {}

M.current = nil

local git = require('regroup.git')

function M.notify(msg, level)
  vim.notify(msg, level or vim.log.levels.INFO)
end

function M.key(config)
  return table.concat({ config.granularity, config.model, config.context }, '|')
end

local function nil_or(v)
  if v == vim.NIL then return nil end
  return v
end

-- a --json payload owns the engine's stdout; anything else in it is a broken seam
function M.decode(raw)
  local ok, data = pcall(vim.json.decode, raw)
  if not ok then error('regroup: unreadable engine listing — ' .. vim.trim(raw), 0) end
  return data
end

local function listing(raw)
  local data = M.decode(raw)
  data.last = nil_or(data.last)
  return data
end

function M.fetch(root)
  return listing(git.engine_ok(root, { 'list', '--json' }))
end

-- cached runs, newest first
function M.runs(data)
  local out = {}
  for key, e in pairs(data.runs) do
    table.insert(out, { key = key, config = e.config, ids = e.ids, patches = e.patches, time = nil_or(e.time) })
  end
  table.sort(out, function(a, b) return (a.time or 0) > (b.time or 0) end)
  return out
end

-- gitsigns diffs against a base it caches per buffer; a write outside the buffer moves it
function M.refresh_signs()
  local gs = package.loaded.gitsigns
  if gs then pcall(gs.reset_base, true) end
end

-- Patch tables are held by open pickers and st.pos, so a fresh listing is carried into
-- the existing tables, matched by id, instead of swapping them out.
local function adopt(st, patches)
  local old = {}
  for _, p in ipairs(st.patches) do old[p.id] = p end
  st.patches = {}
  for _, p in ipairs(patches) do
    local keep = old[p.id]
    if keep then
      for k, v in pairs(p) do keep[k] = v end
      keep.mixed = p.mixed
      p = keep
    end
    table.insert(st.patches, p)
  end
end

local function by_seq(a, b) return a.seq < b.seq end

-- Each patch gets `live`, its hunks still in the diff in diff order; hunks no patch covers
-- fill the session's one synthetic patch, shown last while it has any.
local function take(st, data)
  st.branch = data.branch
  st.drifted = data.last ~= nil and M.key(data.last) ~= st.key
  st.hunks = data.hunks
  st.by_id, st.staged = {}, {}
  for i, h in ipairs(st.hunks) do
    h.seq = i
    st.by_id[h.id] = h
  end
  for _, id in ipairs(data.staged) do st.staged[id] = true end
  local entry = data.runs[st.key]
  adopt(st, entry and entry.patches or {})
  local assigned = {}
  st.shown = {}
  for _, p in ipairs(st.patches) do
    p.live = {}
    for _, id in ipairs(p.hunks) do
      local h = st.by_id[id]
      if h then
        assigned[id] = true
        table.insert(p.live, h)
      end
    end
    table.sort(p.live, by_seq)
    table.insert(st.shown, p)
  end
  local stray = st.stray
  stray.hunks, stray.live = {}, {}
  for _, h in ipairs(st.hunks) do
    if not assigned[h.id] then
      table.insert(stray.hunks, h.id)
      table.insert(stray.live, h)
    end
  end
  if #stray.live > 0 then table.insert(st.shown, stray) end
end

-- Open the run `config` names (the engine's current one when nil) from `data`, or from a
-- fresh listing; a run the engine has pruned meanwhile loads with no patches, its
-- remaining hunks showing as unassigned.
function M.load(root, config, data)
  data = data or M.fetch(root)
  config = config or data.last
  if not config then return nil end
  local key = M.key(config)
  local st = M.current
  if not (st and st.root == root and st.key == key) then
    st = {
      root = root, config = config, key = key, patches = {},
      stray = { id = '', title = '(unassigned new changes)', message = '', hunks = {}, stray = true },
    }
    M.current = st
  end
  take(st, data)
  return st
end

function M.refresh(st)
  take(st, M.fetch(st.root))
end

local function refresh_async(st)
  git.engine(st.root, { 'list', '--json' }, function(res)
    if res.code ~= 0 or M.current ~= st then return end
    local ok, data = pcall(listing, res.stdout)
    if ok then take(st, data) end
  end)
end

-- The engine's patch commands act on the run it last used; a shell or agent may have
-- moved that since the listing, so the session re-points it before writing.
function M.point(st)
  if not st.drifted then return true end
  local c = st.config
  local res = git.engine(st.root, { 'use', c.granularity, c.model, c.context })
  if res.code ~= 0 then return false, git.output(res) end
  st.drifted = false
  return true
end

-- after an engine write: the session, the signs and the buffers catch up
function M.after_write(root)
  local st = M.current
  if st and (not root or st.root == root) then
    local ok, err = pcall(M.refresh, st)
    if not ok then M.notify('regroup: stale view — ' .. tostring(err), vim.log.levels.ERROR) end
  end
  M.refresh_signs()
  vim.cmd('checktime')
end

-- after a change made elsewhere (a save, a git command, another window): the same, async
function M.sync(file)
  local st = M.current
  if st and (not file or vim.startswith(file, st.root .. '/')) then refresh_async(st) end
end

function M.touch()
  M.refresh_signs()
  M.sync()
end

return M
