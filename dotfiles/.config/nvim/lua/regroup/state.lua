local M = {}

M.current = nil
M.synced = {}  -- root -> id signature last handed to `dienpy hunks sync`

local function cache_path(root)
  return root .. '/.git/regroup-cache.json'
end

function M.key(config)
  return table.concat({ config.granularity, config.model, config.context }, '|')
end

local function read_cache(root)
  local f = io.open(cache_path(root), 'r')
  if not f then return nil end
  local ok, data = pcall(vim.json.decode, f:read('*a'))
  f:close()
  -- v2 entries predate the rebind anchors; the engine adds those on its next write
  if not ok or type(data) ~= 'table' or (data.version ~= 3 and data.version ~= 2) then return nil end
  return data
end

local function write_cache(root, data)
  data.version = 3
  local f = assert(io.open(cache_path(root), 'w'))
  f:write(vim.json.encode(data))
  f:close()
end

local function id_delta(st)
  local live, grouped = {}, {}
  local d = { stray = {}, missing = {} }
  for _, h in ipairs(st.parse.hunks) do live[h.id] = true end
  for _, g in ipairs(st.groups) do
    for _, id in ipairs(g.hunks) do
      grouped[id] = true
      if not live[id] then table.insert(d.missing, id) end
    end
  end
  for _, h in ipairs(st.parse.hunks) do
    if not grouped[h.id] then table.insert(d.stray, h.id) end
  end
  d.sig = table.concat(d.stray, ',') .. '|' .. table.concat(d.missing, ',')
  return d
end

local function drop_missing(st, missing)
  local dead = {}
  for _, id in ipairs(missing) do dead[id] = true end
  for _, g in ipairs(st.groups) do
    g.hunks = vim.tbl_filter(function(id) return not dead[id] end, g.hunks)
  end
end

-- Group tables are held by open pickers and st.pos, so carry the engine's result
-- into the existing tables instead of swapping them out.
local function adopt(st, groups)
  local same = #groups == #st.groups
  for i, g in ipairs(groups) do
    if same and g.title ~= st.groups[i].title then same = false end
  end
  if not same then
    st.groups = groups
    return
  end
  for i, g in ipairs(groups) do
    st.groups[i].hunks = g.hunks
    st.groups[i].mixed = g.mixed
    st.groups[i].ambiguous = g.ambiguous
  end
end

local inflight = {}

-- Bring a run up to date: rebind edited hunks and let the model place the ones the run
-- has never seen. The config comes from the cache entry, so nvim only ever forwards it.
function M.extend(root, config, cb)
  if inflight[root] then
    return vim.notify('regroup: an update is already running here', vim.log.levels.WARN)
  end
  inflight[root] = true
  vim.notify(('regroup: extending [%s] — placing the unassigned hunks...'):format(M.key(config)))
  vim.system({ 'dienpy', 'hunks', 'run', '--extend',
    config.granularity, config.model, config.context },
    { text = true, cwd = root },
    vim.schedule_wrap(function(res)
      inflight[root] = nil
      if res.code ~= 0 then
        return vim.notify('regroup: extend failed\n' ..
          vim.trim((res.stderr or '') .. (res.stdout or '')), vim.log.levels.ERROR)
      end
      cb()
    end))
end

local function run_sync(root)
  local res = vim.system({ 'dienpy', 'hunks', 'sync' }, { text = true, cwd = root }):wait()
  if res.code == 0 then return true end
  vim.notify('regroup: dienpy hunks sync failed\n' ..
    vim.trim((res.stderr or '') .. (res.stdout or '')), vim.log.levels.WARN)
  return false
end

-- Reconcile every cached run before the menu reports coverage, so an edited hunk
-- reads as cached rather than as a new one needing the model.
function M.sync_cache(root, parse)
  local data = read_cache(root)
  if not data or not data.analyses then return end
  local live, ids = {}, {}
  for _, h in ipairs(parse.hunks) do
    live[h.id] = true
    table.insert(ids, h.id)
  end
  local drift, known = false, {}
  for _, entry in pairs(data.analyses) do
    for _, id in ipairs(entry.ids) do
      known[id] = true
      table.insert(ids, id)
      if not live[id] then drift = true end
    end
  end
  for _, h in ipairs(parse.hunks) do
    if not known[h.id] then drift = true end
  end
  table.sort(ids)  -- pairs() over analyses is unordered; the memo needs a stable signature
  local sig = table.concat(ids, ',')
  if not drift or M.synced[root] == sig then return end
  M.synced[root] = sig
  run_sync(root)
end

-- Edits mint new hunk ids; `dienpy hunks sync` rebinds them to their groups by
-- HEAD-side anchor. Runs only when the live and grouped id sets disagree.
function M.reconcile(st)
  local d = id_delta(st)
  if d.sig == '|' then return end
  if #d.stray == 0 then
    -- committed / buried / reverted: nothing to rebind, just forget the dead ids
    -- (the cache sheds them on the next engine run)
    return drop_missing(st, d.missing)
  end
  local function adopt_cache()
    local entry = M.entry(st.parse.root, st.config)
    if entry then adopt(st, entry.groups) end
  end
  adopt_cache()  -- someone (sync_cache, a shell `hunks run`) may have done the work already
  d = id_delta(st)
  if d.sig == '|' or st.reconciled == d.sig then return end
  st.reconciled = d.sig
  if not run_sync(st.parse.root) then return end
  adopt_cache()
  local after = id_delta(st)
  st.reconciled = after.sig
  local carried = #d.stray - #after.stray
  if carried > 0 then
    vim.notify(('regroup: carried %d edited hunk(s) into their groups'):format(carried))
  end
end

function M.refresh(st)
  st.parse = require('regroup.diff').parse(st.parse.root)
  M.reconcile(st)
end

function M.last_config(root)
  local data = read_cache(root)
  return data and data.last or nil
end

function M.entry(root, config)
  local data = read_cache(root)
  return data and data.analyses and data.analyses[M.key(config)] or nil
end

-- Open a cached run, carrying the cache into the live session when it is the same run:
-- pickers and st.pos hold those group tables. Hunks the run does not cover surface as
-- "(unassigned new changes)" rather than barring the load.
function M.load(root, parse, config)
  local entry = M.entry(root, config)
  if not entry then return nil end
  M.touch_last(root, config)
  local st = M.current
  if st and st.parse.root == root and M.key(st.config) == M.key(config) then
    st.parse = parse
    adopt(st, entry.groups)
    M.reconcile(st)
  else
    M.current = { parse = parse, groups = entry.groups, config = config }
  end
  return M.current
end

function M.runs(root)
  local data = read_cache(root)
  if not data then return {} end
  local out = {}
  for key, entry in pairs(data.analyses) do
    local config = entry.config
    if not config or config == vim.NIL then
      local parts = vim.split(key, '|', { plain = true })
      config = { granularity = parts[1], model = parts[2], context = parts[3] }
    end
    table.insert(out, {
      key = key,
      config = config,
      ids = entry.ids,
      groups = entry.groups,
      time = entry.time ~= vim.NIL and entry.time or nil,
    })
  end
  table.sort(out, function(a, b) return (a.time or 0) > (b.time or 0) end)
  return out
end

function M.mark_group(st, g, marks)
  for k, v in pairs(marks) do g[k] = v end
  local idx
  for i, sg in ipairs(st.groups) do
    if sg == g then idx = i end
  end
  if not idx then return end
  local data = read_cache(st.parse.root)
  local entry = data and data.analyses and data.analyses[M.key(st.config)]
  local eg = entry and entry.groups and entry.groups[idx]
  if eg and eg.title == g.title then
    for k, v in pairs(marks) do eg[k] = v end
    write_cache(st.parse.root, data)
  end
end

-- Persist manual hunk moves. Refuses if the cached run drifted from the session
-- (someone re-ran the engine meanwhile) rather than clobbering it.
function M.write_groups(st)
  local data = read_cache(st.parse.root)
  local entry = data and data.analyses and data.analyses[M.key(st.config)]
  if not entry or #entry.groups ~= #st.groups then return false end
  for i, g in ipairs(st.groups) do
    if entry.groups[i].title ~= g.title then return false end
    entry.groups[i].hunks = g.hunks
    entry.groups[i].ambiguous = g.ambiguous
  end
  write_cache(st.parse.root, data)
  return true
end

function M.touch_last(root, config)
  local data = read_cache(root)
  if not data then return end
  data.last = config
  write_cache(root, data)
end

return M
