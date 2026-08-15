local M = {}

M.current = nil

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
  if not ok or type(data) ~= 'table' or data.version ~= 2 then return nil end
  return data
end

local function write_cache(root, data)
  local f = assert(io.open(cache_path(root), 'w'))
  f:write(vim.json.encode(data))
  f:close()
end

function M.refresh(st)
  st.parse = require('regroup.diff').parse(st.parse.root)
end

function M.last_config(root)
  local data = read_cache(root)
  return data and data.last or nil
end

function M.entry(root, config)
  local data = read_cache(root)
  return data and data.analyses and data.analyses[M.key(config)] or nil
end

function M.load_cache(root, parse, config)
  local entry = M.entry(root, config)
  if not entry then return nil end
  local known = {}
  for _, id in ipairs(entry.ids) do known[id] = true end
  for _, h in ipairs(parse.hunks) do
    if not known[h.id] then return nil end
  end
  return entry.groups
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

function M.touch_last(root, config)
  local data = read_cache(root)
  if not data then return end
  data.last = config
  write_cache(root, data)
end

return M
