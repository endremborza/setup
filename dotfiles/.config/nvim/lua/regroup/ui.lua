local M = {}

local diff = require('regroup.diff')
local state = require('regroup.state')
local review = require('regroup.review')

local function notify(msg, level)
  vim.notify(msg, level or vim.log.levels.INFO)
end

local function refresh_signs()
  local gs = package.loaded.gitsigns
  if gs then pcall(gs.reset_base, true) end
end

local function live_recs(st, g)
  local out = {}
  for _, id in ipairs(g.hunks) do
    local h = st.parse.by_id[id]
    if h then table.insert(out, h) end
  end
  table.sort(out, function(a, b)
    if a.fi ~= b.fi then return a.fi < b.fi end
    return a.hi < b.hi
  end)
  return out
end

local function split_live(st, g)
  local live, missing = {}, {}
  for _, id in ipairs(g.hunks) do
    if st.parse.by_id[id] then
      table.insert(live, id)
    else
      table.insert(missing, id)
    end
  end
  return live, missing
end

local function check_drift(live, missing)
  if #missing > 0 and #live > 0 then
    error(('%d hunk(s) missing from the current diff (edited since analysis?): %s — :Regroup! to re-analyze')
      :format(#missing, table.concat(missing, ', ')), 0)
  end
end

local function display_groups(st)
  local assigned = {}
  for _, g in ipairs(st.groups) do
    for _, id in ipairs(g.hunks) do assigned[id] = true end
  end
  local stray = {}
  for _, h in ipairs(st.parse.hunks) do
    if not assigned[h.id] then table.insert(stray, h.id) end
  end
  local out = vim.list_slice(st.groups)
  if #stray > 0 then
    table.insert(out, { title = '(unassigned new changes)', message = '', hunks = stray, stray = true })
  end
  return out
end

function M.goto_hunk(g, idx)
  local st = state.current
  state.refresh(st)
  local live = live_recs(st, g)
  if #live == 0 then
    return notify('group has no remaining hunks (already committed)', vim.log.levels.WARN)
  end
  idx = ((idx - 1) % #live) + 1
  st.pos = { group = g, idx = idx }
  local h = live[idx]
  review.base = 'HEAD'
  review.jump(st.parse.root .. '/' .. h.path, h.new_start)
  notify(('[%d/%d] %s'):format(idx, #live, g.title))
end

function M.nav(dir)
  local st = state.current
  if not st or not st.pos then
    return notify('no active change group — run :Regroup', vim.log.levels.WARN)
  end
  M.goto_hunk(st.pos.group, st.pos.idx + dir)
end

function M.stage_group(g)
  local st = state.current
  local ok, err = pcall(function()
    state.refresh(st)
    local live, missing = split_live(st, g)
    check_drift(live, missing)
    if #live == 0 then error('group already committed', 0) end
    local cachedp = diff.parse(st.parse.root, { cached = true })
    local to_stage = {}
    for _, id in ipairs(live) do
      if not cachedp.by_id[id] then table.insert(to_stage, id) end
    end
    if #to_stage == 0 then error('group already staged', 0) end
    diff.stage(st.parse, to_stage)
    g.staged = true
    refresh_signs()
    notify(('staged %d hunk(s): %s'):format(#to_stage, g.title))
  end)
  if not ok then notify(err, vim.log.levels.ERROR) end
end

function M.unstage_group(g)
  local st = state.current
  local ok, err = pcall(function()
    local cachedp = diff.parse(st.parse.root, { cached = true })
    local staged = {}
    for _, id in ipairs(g.hunks) do
      if cachedp.by_id[id] then table.insert(staged, id) end
    end
    if #staged == 0 then error('nothing from this group is staged', 0) end
    diff.unstage(cachedp, staged)
    g.staged = false
    refresh_signs()
    notify(('unstaged %d hunk(s): %s'):format(#staged, g.title))
  end)
  if not ok then notify(err, vim.log.levels.ERROR) end
end

local function check_foreign(st, g, cachedp)
  local gset = {}
  for _, id in ipairs(g.hunks) do gset[id] = true end
  for _, h in ipairs(cachedp.hunks) do
    if not gset[h.id] then
      error(('index contains changes outside this group (%s %s) — commit or unstage those first')
        :format(h.id, h.path), 0)
    end
  end
end

local function open_commit_buffer(g, hunk_lines, on_write)
  local existing = vim.fn.bufnr('regroup://commit')
  if existing ~= -1 then vim.api.nvim_buf_delete(existing, { force = true }) end
  local buf = vim.api.nvim_create_buf(false, false)
  vim.api.nvim_buf_set_name(buf, 'regroup://commit')

  local lines = { g.title, '' }
  for _, l in ipairs(vim.split(g.message or '', '\n', { plain = true })) do
    table.insert(lines, l)
  end
  table.insert(lines, '')
  table.insert(lines, '# Committing change group. Write (:w) to commit, quit to abort.')
  vim.list_extend(lines, hunk_lines)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)

  vim.bo[buf].buftype = 'acwrite'
  vim.bo[buf].bufhidden = 'wipe'
  vim.bo[buf].filetype = 'gitcommit'
  vim.bo[buf].modified = false

  vim.api.nvim_create_autocmd('BufWriteCmd', {
    buffer = buf,
    callback = function()
      local msg = {}
      for _, l in ipairs(vim.api.nvim_buf_get_lines(buf, 0, -1, false)) do
        if not l:match('^#') then table.insert(msg, l) end
      end
      while #msg > 0 and msg[#msg] == '' do table.remove(msg) end
      if #msg == 0 then
        return notify('empty commit message', vim.log.levels.ERROR)
      end
      local ok, err = pcall(on_write, table.concat(msg, '\n') .. '\n')
      if ok then
        vim.bo[buf].modified = false
        vim.api.nvim_buf_delete(buf, { force = true })
      else
        notify(err, vim.log.levels.ERROR)
      end
    end,
  })

  vim.cmd('botright split')
  vim.api.nvim_win_set_buf(0, buf)
  vim.api.nvim_win_set_height(0, math.min(#lines + 2, 15))
end

function M.commit_group(g)
  local st = state.current
  local ok, err = pcall(function()
    state.refresh(st)
    local live, missing = split_live(st, g)
    check_drift(live, missing)
    local cachedp = diff.parse(st.parse.root, { cached = true })
    check_foreign(st, g, cachedp)
    if #live == 0 and #cachedp.hunks == 0 then error('group already committed', 0) end
  end)
  if not ok then return notify(err, vim.log.levels.ERROR) end

  local hunk_lines = {}
  for _, h in ipairs(live_recs(st, g)) do
    table.insert(hunk_lines, ('#   %s (%s)'):format(h.path, h.id))
  end

  open_commit_buffer(g, hunk_lines, function(msg)
    state.refresh(st)
    local live, missing = split_live(st, g)
    check_drift(live, missing)
    local cachedp = diff.parse(st.parse.root, { cached = true })
    check_foreign(st, g, cachedp)
    local to_stage = {}
    for _, id in ipairs(live) do
      if not cachedp.by_id[id] then table.insert(to_stage, id) end
    end
    if #to_stage > 0 then diff.stage(st.parse, to_stage) end
    local res = vim.system({ 'git', 'commit', '-F', '-' }, { text = true, cwd = st.parse.root, stdin = msg }):wait()
    assert(res.code == 0, 'git commit failed:\n' .. (res.stderr or '') .. (res.stdout or ''))
    state.refresh(st)
    refresh_signs()
    local short = vim.trim(vim.system({ 'git', 'rev-parse', '--short', 'HEAD' }, { text = true, cwd = st.parse.root }):wait().stdout)
    notify(('✓ %s %s'):format(short, msg:match('^[^\n]*')))
  end)
end

local function group_preview(st, g, bufnr)
  local lines = { '# ' .. g.title, '' }
  for _, l in ipairs(vim.split(g.message or '', '\n', { plain = true })) do
    table.insert(lines, l)
  end
  if g.mixed and #g.mixed > 0 then
    table.insert(lines, '')
    for _, m in ipairs(g.mixed) do
      table.insert(lines, ('# MIXED %s: %s'):format(m.hunk, m.note))
    end
  end
  for _, h in ipairs(live_recs(st, g)) do
    table.insert(lines, '')
    table.insert(lines, ('# [%s] %s'):format(h.id, h.path))
    for _, l in ipairs(vim.split(diff.hunk_text(h), '\n', { plain = true })) do
      table.insert(lines, l)
    end
  end
  vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)
  vim.bo[bufnr].filetype = 'diff'
end

function M.pick_groups()
  local st = state.current
  if not st then
    return notify('no regroup analysis — run :Regroup', vim.log.levels.WARN)
  end
  local pickers = require('telescope.pickers')
  local finders = require('telescope.finders')
  local conf = require('telescope.config').values
  local previewers = require('telescope.previewers')
  local actions = require('telescope.actions')
  local action_state = require('telescope.actions.state')

  pickers.new({}, {
    prompt_title = ('change groups [%s]  <cr> browse | <c-h> hunks | ◀ ▶ un/stage | <c-y> commit'):format(st.granularity),
    finder = finders.new_table {
      results = display_groups(st),
      entry_maker = function(g)
        local n = #live_recs(st, g)
        local tag
        if n == 0 then
          tag = '✓ done'
        elseif g.stray then
          tag = '? new'
        elseif g.staged then
          tag = '● staged'
        else
          tag = n .. ' hunk' .. (n == 1 and '' or 's')
        end
        return {
          value = g,
          display = ('%-9s %s'):format(tag, g.title),
          ordinal = g.title .. ' ' .. (g.message or ''),
        }
      end,
    },
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'group',
      define_preview = function(self, entry)
        group_preview(st, entry.value, self.state.bufnr)
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local function with_sel(fn)
        return function()
          local entry = action_state.get_selected_entry()
          if not entry then return end
          actions.close(prompt_bufnr)
          fn(entry.value)
        end
      end
      local mappings = {
        ['<CR>'] = with_sel(function(g) M.goto_hunk(g, 1) end),
        ['<C-h>'] = with_sel(function(g) M.pick_hunks(g) end),
        ['<Right>'] = with_sel(M.stage_group),
        ['<Left>'] = with_sel(M.unstage_group),
        ['<C-y>'] = with_sel(M.commit_group),
      }
      for key, fn in pairs(mappings) do
        map('i', key, fn)
        map('n', key, fn)
      end
      return true
    end,
  }):find()
end

function M.pick_hunks(g)
  local st = state.current
  local pickers = require('telescope.pickers')
  local finders = require('telescope.finders')
  local conf = require('telescope.config').values
  local previewers = require('telescope.previewers')
  local actions = require('telescope.actions')
  local action_state = require('telescope.actions.state')

  local results = {}
  for i, h in ipairs(live_recs(st, g)) do
    table.insert(results, { i = i, h = h })
  end

  pickers.new({}, {
    prompt_title = g.title,
    finder = finders.new_table {
      results = results,
      entry_maker = function(it)
        local first = ''
        if it.h.hunk then
          for _, l in ipairs(it.h.hunk.lines) do
            if l:match('^[%+%-]') then
              first = l
              break
            end
          end
        end
        return {
          value = it,
          display = ('%s:%d  %s'):format(it.h.path, it.h.new_start, first),
          ordinal = it.h.path .. ' ' .. first,
        }
      end,
    },
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'hunk',
      define_preview = function(self, entry)
        vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false,
          vim.split(diff.hunk_text(entry.value.h), '\n', { plain = true }))
        vim.bo[self.state.bufnr].filetype = 'diff'
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local function select()
        local entry = action_state.get_selected_entry()
        if not entry then return end
        actions.close(prompt_bufnr)
        M.goto_hunk(g, entry.value.i)
      end
      map('i', '<CR>', select)
      map('n', '<CR>', select)
      return true
    end,
  }):find()
end

return M
