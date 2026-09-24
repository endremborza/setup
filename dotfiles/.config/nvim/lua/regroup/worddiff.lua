local M = {}

local ns = vim.api.nvim_create_namespace('regroup.worddiff')

-- a block whose sides share less than this fraction of their bytes is a rewrite, left unmarked
local MIN_SHARED = 0.5

-- words (UTF-8 letters included) and single punctuation marks; whitespace only separates them,
-- so a whitespace-only edit marks no words and the gap between two changed words is marked with them
local function tokenize(lines, first)
  local toks = { text = {}, row = {}, s = {}, e = {}, bytes = 0 }
  for r = first, first + #lines - 1 do
    local line, i = lines[r - first + 1], 2
    while true do
      local s = line:find('%S', i)
      if not s then break end
      local e = select(2, line:find('^[%w_\128-\255]+', s)) or s
      local n = #toks.text + 1
      toks.text[n], toks.row[n], toks.s[n], toks.e[n] = line:sub(s, e), r, s - 1, e
      toks.bytes = toks.bytes + e - s + 1
      i = e + 1
    end
  end
  return toks
end

-- the changed tokens [from, from + count) as one mark per row, reporting the bytes they cover
local function spans(toks, from, count, hl, out)
  local bytes = 0
  for k = from, from + count - 1 do
    bytes = bytes + toks.e[k] - toks.s[k]
    local last = out[#out]
    if last and last.row == toks.row[k] and last.k == k - 1 then
      last.e, last.k = toks.e[k], k
    else
      table.insert(out, { row = toks.row[k], s = toks.s[k], e = toks.e[k], k = k, hl = hl })
    end
  end
  return bytes
end

local function mark_block(buf, del, add)
  local changed = {}
  local diff = vim.text.diff(table.concat(del.text, '\n') .. '\n', table.concat(add.text, '\n') .. '\n',
    { result_type = 'indices', algorithm = 'histogram' })
  local changed_bytes = 0
  for _, d in ipairs(diff) do
    changed_bytes = changed_bytes + spans(del, d[1], d[2], 'DiffDelete', changed)
      + spans(add, d[3], d[4], 'DiffAdd', changed)
  end
  local total = del.bytes + add.bytes
  if total == 0 or (total - changed_bytes) / total < MIN_SHARED then return end
  for _, m in ipairs(changed) do
    vim.api.nvim_buf_set_extmark(buf, ns, m.row, m.s, { end_col = m.e, hl_group = m.hl })
  end
end

-- Marks the changed words of every removed/added line pair in a unified diff buffer.
-- Linear in the buffer plus one token-level diff per run of -/+ lines.
function M.highlight(buf)
  vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  local in_hunk, r = false, 1
  while r <= #lines do
    local c = lines[r]:sub(1, 1)
    if lines[r]:sub(1, 2) == '@@' then
      in_hunk = true
    elseif c ~= ' ' and c ~= '-' and c ~= '+' and c ~= '\\' then
      in_hunk = false
    end
    if in_hunk and c == '-' then
      local d = r
      while lines[d + 1] and lines[d + 1]:sub(1, 1) == '-' do d = d + 1 end
      local a = d
      while lines[a + 1] and lines[a + 1]:sub(1, 1) == '+' do a = a + 1 end
      if a > d then
        mark_block(buf, tokenize(vim.list_slice(lines, r, d), r - 1), tokenize(vim.list_slice(lines, d + 1, a), d))
      end
      r = a
    end
    r = r + 1
  end
end

return M
