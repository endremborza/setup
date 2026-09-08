local M = {}

M.current = nil

local git = require('regroup.git')

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

function M.fetch(root)
  local data = M.decode(git.engine_ok(root, { 'list', '--json' }))
  data.last = nil_or(data.last)
  return data
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

local function take(st, data)
  st.branch = data.branch
  st.last = data.last
  st.hunks = data.hunks
  st.by_id, st.staged = {}, {}
  for i, h in ipairs(st.hunks) do
    h.seq = i
    st.by_id[h.id] = h
  end
  for _, id in ipairs(data.staged) do st.staged[id] = true end
  local entry = data.runs[st.key]
  adopt(st, entry and entry.patches or {})
end

-- Open the run `config` names (the engine's current one when nil); a run the engine has
-- pruned meanwhile loads with no patches, its remaining hunks showing as unassigned.
function M.load(root, config)
  local data = M.fetch(root)
  config = config or data.last
  if not config then return nil end
  local key = M.key(config)
  local st = M.current
  if not (st and st.root == root and st.key == key) then
    st = { root = root, config = config, key = key, patches = {} }
    M.current = st
  end
  take(st, data)
  return st
end

function M.refresh(st)
  take(st, M.fetch(st.root))
end

return M
