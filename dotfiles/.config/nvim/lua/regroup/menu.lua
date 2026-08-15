local M = {}

local DIMS = { 'granularity', 'model', 'context' }

function M.open(opts)
  local sel = {}
  for _, dim in ipairs(DIMS) do
    sel[dim] = 1
    for i, v in ipairs(opts.values[dim]) do
      if v == opts.initial[dim] then sel[dim] = i end
    end
  end
  local row = 1

  local width = 66
  for _, dim in ipairs(DIMS) do
    local w = 18
    for _, v in ipairs(opts.values[dim]) do w = w + #v + 3 end
    width = math.max(width, w)
  end

  local buf = vim.api.nvim_create_buf(false, true)
  vim.bo[buf].bufhidden = 'wipe'
  local win = vim.api.nvim_open_win(buf, true, {
    relative = 'editor',
    style = 'minimal',
    border = 'rounded',
    width = width,
    height = #DIMS + 4,
    row = math.floor((vim.o.lines - (#DIMS + 6)) / 2),
    col = math.floor((vim.o.columns - width) / 2),
    title = opts.title or ' regroup ',
    title_pos = 'center',
  })

  local function config()
    local c = {}
    for _, dim in ipairs(DIMS) do
      c[dim] = opts.values[dim][sel[dim]]
    end
    return c
  end

  local function render()
    local lines = { '' }
    for di, dim in ipairs(DIMS) do
      local parts = {}
      for i, v in ipairs(opts.values[dim]) do
        table.insert(parts, i == sel[dim] and ('[' .. v .. ']') or (' ' .. v .. ' '))
      end
      table.insert(lines, (' %s %-12s %s'):format(di == row and '▸' or ' ', dim, table.concat(parts, ' ')))
    end
    table.insert(lines, '')
    table.insert(lines, '  ' .. opts.info(config()))
    table.insert(lines, '  ⏎ run   R re-analyze' .. (opts.on_runs and '   p runs' or '')
      .. (opts.on_graveyard and '   g graveyard' or '') .. '   h/l   j/k   ? help   q quit')
    vim.bo[buf].modifiable = true
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
    vim.bo[buf].modifiable = false
  end

  local function close()
    if vim.api.nvim_win_is_valid(win) then vim.api.nvim_win_close(win, true) end
  end

  local function confirm(force)
    local c = config()
    close()
    opts.on_confirm(c, force)
  end

  local function move(d)
    row = (row - 1 + d) % #DIMS + 1
    render()
  end

  local function cycle(d)
    local dim = DIMS[row]
    sel[dim] = (sel[dim] - 1 + d) % #opts.values[dim] + 1
    render()
  end

  local function map(lhs, fn)
    vim.keymap.set('n', lhs, fn, { buffer = buf, nowait = true })
  end
  map('j', function() move(1) end)
  map('k', function() move(-1) end)
  map('<Down>', function() move(1) end)
  map('<Up>', function() move(-1) end)
  map('l', function() cycle(1) end)
  map('h', function() cycle(-1) end)
  map('<Right>', function() cycle(1) end)
  map('<Left>', function() cycle(-1) end)
  map('<CR>', function() confirm(false) end)
  map('R', function() confirm(true) end)
  if opts.on_runs then
    map('p', function()
      close()
      opts.on_runs()
    end)
  end
  if opts.on_graveyard then
    map('g', function()
      close()
      opts.on_graveyard()
    end)
  end
  map('?', function()
    close()
    vim.cmd('help regroup')
  end)
  map('q', close)
  map('<Esc>', close)

  render()
end

return M
