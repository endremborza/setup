local M = {}

M.current = nil

local function cache_path(root)
  return root .. '/.git/regroup-cache.json'
end

function M.refresh(st)
  st.parse = require('regroup.diff').parse(st.parse.root)
end

function M.save_cache(st)
  local ids = {}
  for _, h in ipairs(st.parse.hunks) do
    table.insert(ids, h.id)
  end
  local f = assert(io.open(cache_path(st.parse.root), 'w'))
  f:write(vim.json.encode({ version = 1, granularity = st.granularity, ids = ids, groups = st.groups }))
  f:close()
end

function M.load_cache(root, parse, granularity)
  local f = io.open(cache_path(root), 'r')
  if not f then return nil end
  local ok, data = pcall(vim.json.decode, f:read('*a'))
  f:close()
  if not ok or type(data) ~= 'table' or data.version ~= 1 or data.granularity ~= granularity then
    return nil
  end
  local known = {}
  for _, id in ipairs(data.ids) do known[id] = true end
  for _, h in ipairs(parse.hunks) do
    if not known[h.id] then return nil end
  end
  return data.groups
end

return M
