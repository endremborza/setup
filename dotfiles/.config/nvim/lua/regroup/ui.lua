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
    error(('%d hunk(s) missing from the current diff and not rebindable: %s — dienpy hunks sync, or :Regroup! to re-analyze')
      :format(#missing, table.concat(missing, ', ')), 0)
  end
end

local function ambiguous_set(st, g)
  local out = {}
  for _, id in ipairs(g.ambiguous or {}) do
    if st.parse.by_id[id] then out[id] = true end
  end
  return out
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
    return notify('group has no remaining hunks (committed or discarded)', vim.log.levels.WARN)
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

local function same_group(a, b)
  return a == b or (a and b and a.stray and b.stray) or false
end

function M.nav_group(dir)
  local st = state.current
  if not st or not st.pos then
    return notify('no active change group — run :Regroup', vim.log.levels.WARN)
  end
  state.refresh(st)
  local live = {}
  for _, g in ipairs(display_groups(st)) do
    if #live_recs(st, g) > 0 then table.insert(live, g) end
  end
  if #live == 0 then
    return notify('no groups with remaining hunks', vim.log.levels.WARN)
  end
  local cur = 1
  for i, g in ipairs(live) do
    if same_group(g, st.pos.group) then cur = i end
  end
  local nxt = live[((cur - 1 + dir) % #live) + 1]
  M.goto_hunk(nxt, 1)
end

function M.reopen()
  local st = state.current
  if not st then
    return notify('no regroup analysis — run :Regroup', vim.log.levels.WARN)
  end
  M.pick_groups({ select = st.pos and st.pos.group })
end

function M.stage_group(g)
  local st = state.current
  local ok, err = pcall(function()
    state.refresh(st)
    local live, missing = split_live(st, g)
    check_drift(live, missing)
    if #live == 0 then error('group has no remaining hunks (committed or discarded)', 0) end
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

function M.stage_hunk(h)
  local st = state.current
  local ok, err = pcall(function()
    state.refresh(st)
    if not st.parse.by_id[h.id] then error('hunk no longer in the diff (edited or committed?)', 0) end
    local cachedp = diff.parse(st.parse.root, { cached = true })
    if cachedp.by_id[h.id] then error('hunk already staged', 0) end
    diff.stage(st.parse, { h.id })
    refresh_signs()
    notify(('staged %s:%d'):format(h.path, h.new_start))
  end)
  if not ok then notify(err, vim.log.levels.ERROR) end
end

function M.unstage_hunk(h)
  local ok, err = pcall(function()
    local st = state.current
    local cachedp = diff.parse(st.parse.root, { cached = true })
    if not cachedp.by_id[h.id] then error('hunk is not staged', 0) end
    diff.unstage(cachedp, { h.id })
    refresh_signs()
    notify(('unstaged %s:%d'):format(h.path, h.new_start))
  end)
  if not ok then notify(err, vim.log.levels.ERROR) end
end

local function after_revert(st)
  state.refresh(st)
  refresh_signs()
  vim.cmd('checktime')
end

function M.revert_group(g)
  local st = state.current
  local ok, err = pcall(function()
    local approx = #split_live(st, g)
    if approx == 0 then error('group has no remaining hunks', 0) end
    if vim.fn.confirm(('Revert %d hunk(s) of "%s" to HEAD? This discards those changes.')
          :format(approx, g.title), '&Yes\n&No', 2) ~= 1 then
      return
    end
    state.refresh(st)
    local live = split_live(st, g)
    if #live == 0 then error('group has no remaining hunks', 0) end
    diff.revert(st.parse, live)
    after_revert(st)
    state.mark_group(st, g, { dropped = true })
    notify(('reverted %d hunk(s): %s'):format(#live, g.title))
  end)
  if not ok then notify(err, vim.log.levels.ERROR) end
end

function M.revert_hunk(h)
  local st = state.current
  local ok, err = pcall(function()
    if vim.fn.confirm(('Revert %s:%d to HEAD? This discards the change.')
          :format(h.path, h.new_start), '&Yes\n&No', 2) ~= 1 then
      return
    end
    state.refresh(st)
    if not st.parse.by_id[h.id] then error('hunk no longer in the diff (edited or committed?)', 0) end
    diff.revert(st.parse, { h.id })
    after_revert(st)
    for _, g in ipairs(st.groups) do
      for _, id in ipairs(g.hunks) do
        if id == h.id and #live_recs(st, g) == 0 and not g.committed then
          state.mark_group(st, g, { dropped = true })
        end
      end
    end
    notify(('reverted %s:%d'):format(h.path, h.new_start))
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

function M.bury_group(g)
  local st = state.current
  local ok, err = pcall(function()
    local approx = #split_live(st, g)
    if approx == 0 then error('group has no remaining hunks', 0) end
    if vim.fn.confirm(('Bury %d hunk(s) of "%s" to the graveyard (git stash)?')
          :format(approx, g.title), '&Yes\n&No', 1) ~= 1 then
      return
    end
    state.refresh(st)
    local live, missing = split_live(st, g)
    check_drift(live, missing)
    if #live == 0 then error('group has no remaining hunks', 0) end
    local cachedp = diff.parse(st.parse.root, { cached = true })
    check_foreign(st, g, cachedp)
    local to_stage = {}
    for _, id in ipairs(live) do
      if not cachedp.by_id[id] then table.insert(to_stage, id) end
    end
    if #to_stage > 0 then diff.stage(st.parse, to_stage) end
    require('regroup.graveyard').bury(st.parse.root, g.title)
    after_revert(st)
    state.mark_group(st, g, { buried = true })
    notify(('⚰ buried %d hunk(s): %s'):format(#live, g.title))
  end)
  if not ok then notify(err, vim.log.levels.ERROR) end
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
    if #live == 0 and #cachedp.hunks == 0 then error('nothing left to commit in this group', 0) end
  end)
  if not ok then return notify(err, vim.log.levels.ERROR) end

  local amb = vim.tbl_keys(ambiguous_set(st, g))
  if #amb > 0 and vim.fn.confirm(
        ('%d hunk(s) landed here by rebind across group boundaries (%s). Commit anyway?')
        :format(#amb, table.concat(amb, ', ')), '&Yes\n&No', 2) ~= 1 then
    return
  end

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
    state.mark_group(st, g, { committed = short })
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
  local amb = ambiguous_set(st, g)
  if next(amb) then
    table.insert(lines, '')
    for id in pairs(amb) do
      table.insert(lines, ('# REBOUND %s: edit spanned group boundaries — <C-h> then <C-m> to move'):format(id))
    end
  end
  for _, h in ipairs(live_recs(st, g)) do
    table.insert(lines, '')
    table.insert(lines, ('# [%s]%s %s'):format(h.id, amb[h.id] and ' ~' or '', h.path))
    for _, l in ipairs(vim.split(diff.hunk_text(h), '\n', { plain = true })) do
      table.insert(lines, l)
    end
  end
  vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines)
  vim.bo[bufnr].filetype = 'diff'
end

local function rel_age(t)
  if not t then return '?' end
  local d = os.time() - t
  if d < 90 then return d .. 's' end
  if d < 5400 then return math.floor(d / 60 + 0.5) .. 'm' end
  if d < 129600 then return math.floor(d / 3600 + 0.5) .. 'h' end
  return math.floor(d / 86400 + 0.5) .. 'd'
end

local function picker_tools(prompt_bufnr, map, make_finder)
  local action_state = require('telescope.actions.state')
  local tools = {}

  function tools.selected()
    local entry = action_state.get_selected_entry()
    return entry and entry.value
  end

  function tools.refresh()
    local p = action_state.get_current_picker(prompt_bufnr)
    local row = p:get_selection_row()
    local callbacks = { unpack(p._completion_callbacks) }
    p:register_completion_callback(function(self)
      self:set_selection(row)
      self._completion_callbacks = callbacks
    end)
    p:refresh(make_finder(), { reset_prompt = false })
  end

  function tools.bind(key, desc, fn)
    for _, mode in ipairs({ 'i', 'n' }) do
      map(mode, key, fn, { desc = desc })
    end
  end

  return tools
end

local function assign(st, h, from, target)
  local function drop(g)
    if not g then return end
    g.hunks = vim.tbl_filter(function(id) return id ~= h.id end, g.hunks)
    if g.ambiguous then
      local keep = vim.tbl_filter(function(id) return id ~= h.id end, g.ambiguous)
      g.ambiguous = #keep > 0 and keep or nil
    end
  end
  for _, g in ipairs(st.groups) do drop(g) end
  drop(from)  -- may be the synthetic "unassigned" group, which is not in st.groups
  table.insert(target.hunks, h.id)
  return state.write_groups(st)
end

function M.move_hunk(h, from)
  local st = state.current
  local targets = vim.tbl_filter(function(g) return g ~= from end, st.groups)
  if #targets == 0 then return notify('no other group to move into', vim.log.levels.WARN) end
  local pickers = require('telescope.pickers')
  local finders = require('telescope.finders')
  local conf = require('telescope.config').values
  local previewers = require('telescope.previewers')
  local actions = require('telescope.actions')

  pickers.new({}, {
    prompt_title = ('move %s:%d →'):format(h.path, h.new_start),
    finder = finders.new_table {
      results = targets,
      entry_maker = function(g)
        return {
          value = g,
          display = ('%2d hunks  %s'):format(#live_recs(st, g), g.title),
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
      local t = picker_tools(prompt_bufnr, map, nil)
      t.bind('<CR>', 'move hunk here', function()
        local g = t.selected()
        if not g then return end
        actions.close(prompt_bufnr)
        if assign(st, h, from, g) then
          notify(('moved %s:%d → %s'):format(h.path, h.new_start, g.title))
        else
          notify('moved in this session only — the cached run drifted, re-run dienpy hunks run to persist',
            vim.log.levels.WARN)
        end
        M.pick_hunks(from)
      end)
      return true
    end,
  }):find()
end

function M.pick_groups(opts)
  opts = opts or {}
  local st = state.current
  if not st then
    return notify('no regroup analysis — run :Regroup', vim.log.levels.WARN)
  end
  local pickers = require('telescope.pickers')
  local finders = require('telescope.finders')
  local conf = require('telescope.config').values
  local previewers = require('telescope.previewers')
  local actions = require('telescope.actions')

  local function entry_maker(g)
    local n = #live_recs(st, g)
    local tag
    if n == 0 then
      if g.committed then
        tag = '✓ ' .. tostring(g.committed):sub(1, 7)
      elseif g.dropped then
        tag = '✗ dropped'
      elseif g.buried then
        tag = '⚰ buried'
      else
        tag = '· gone'
      end
    elseif g.stray then
      tag = '? new'
    elseif g.staged then
      tag = '● staged'
    else
      tag = n .. ' hunk' .. (n == 1 and '' or 's')
    end
    return {
      value = g,
      display = ('%-9s %s%s'):format(tag, next(ambiguous_set(st, g)) and '~ ' or '', g.title),
      ordinal = g.title .. ' ' .. (g.message or ''),
    }
  end

  local function make_finder()
    return finders.new_table { results = display_groups(st), entry_maker = entry_maker }
  end

  local select_index
  if opts.select then
    for i, g in ipairs(display_groups(st)) do
      if same_group(g, opts.select) then select_index = i end
    end
  end

  pickers.new({}, {
    prompt_title = ('%s · groups [%s] — ? for keys'):format(vim.fs.basename(st.parse.root), state.key(st.config)),
    default_selection_index = select_index,
    finder = make_finder(),
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'group',
      define_preview = function(self, entry)
        group_preview(st, entry.value, self.state.bufnr)
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local t = picker_tools(prompt_bufnr, map, make_finder)
      t.bind('<CR>', 'browse group (then ]g/[g)', function()
        local g = t.selected()
        if not g then return end
        actions.close(prompt_bufnr)
        M.goto_hunk(g, 1)
      end)
      t.bind('<C-h>', 'hunks of group', function()
        local g = t.selected()
        if not g then return end
        actions.close(prompt_bufnr)
        M.pick_hunks(g)
      end)
      t.bind('<C-s>', 'stage group', function()
        local g = t.selected()
        if not g then return end
        M.stage_group(g)
        t.refresh()
      end)
      t.bind('<C-u>', 'unstage group', function()
        local g = t.selected()
        if not g then return end
        M.unstage_group(g)
        t.refresh()
      end)
      t.bind('<C-d>', 'revert group (discard changes)', function()
        local g = t.selected()
        if not g then return end
        M.revert_group(g)
        t.refresh()
      end)
      t.bind('<C-y>', 'commit group', function()
        local g = t.selected()
        if not g then return end
        actions.close(prompt_bufnr)
        M.commit_group(g)
      end)
      t.bind('<C-t>', 'bury group (stash to graveyard)', function()
        local g = t.selected()
        if not g then return end
        M.bury_group(g)
        t.refresh()
      end)
      t.bind('<C-e>', 'config menu (re-analyze / switch config)', function()
        actions.close(prompt_bufnr)
        require('regroup').run {}
      end)
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

  local function make_results()
    local cachedp = diff.parse(st.parse.root, { cached = true })
    local amb = ambiguous_set(st, g)
    local out = {}
    for i, h in ipairs(live_recs(st, g)) do
      table.insert(out, { i = i, h = h, staged = cachedp.by_id[h.id] ~= nil, amb = amb[h.id] })
    end
    return out
  end

  local function entry_maker(it)
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
      display = ('%s%s %s:%d  %s'):format(
        it.staged and '●' or ' ', it.amb and '~' or ' ', it.h.path, it.h.new_start, first),
      ordinal = it.h.path .. ' ' .. first,
    }
  end

  local function make_finder()
    return finders.new_table { results = make_results(), entry_maker = entry_maker }
  end

  pickers.new({}, {
    prompt_title = ('%s — <C-g> back'):format(g.title),
    finder = make_finder(),
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
      local t = picker_tools(prompt_bufnr, map, make_finder)
      t.bind('<CR>', 'jump to hunk', function()
        local it = t.selected()
        if not (it and it.h) then return end
        actions.close(prompt_bufnr)
        M.goto_hunk(g, it.i)
      end)
      t.bind('<C-g>', 'back to groups', function()
        actions.close(prompt_bufnr)
        M.pick_groups({ select = g })
      end)
      t.bind('<C-o>', 'move hunk to another group', function()
        local it = t.selected()
        if not (it and it.h) then return end
        actions.close(prompt_bufnr)
        M.move_hunk(it.h, g)
      end)
      t.bind('<C-s>', 'stage hunk', function()
        local it = t.selected()
        if not (it and it.h) then return end
        M.stage_hunk(it.h)
        t.refresh()
      end)
      t.bind('<C-u>', 'unstage hunk', function()
        local it = t.selected()
        if not (it and it.h) then return end
        M.unstage_hunk(it.h)
        t.refresh()
      end)
      t.bind('<C-d>', 'revert hunk (discard change)', function()
        local it = t.selected()
        if not (it and it.h) then return end
        M.revert_hunk(it.h)
        t.refresh()
      end)
      return true
    end,
  }):find()
end

function M.pick_graveyard()
  local ok, root = pcall(diff.root)
  if not ok then return notify(root, vim.log.levels.ERROR) end
  local gy = require('regroup.graveyard')
  if #gy.list(root) == 0 then
    return notify('graveyard is empty (no regroup stashes)', vim.log.levels.INFO)
  end

  local pickers = require('telescope.pickers')
  local finders = require('telescope.finders')
  local conf = require('telescope.config').values
  local previewers = require('telescope.previewers')
  local actions = require('telescope.actions')

  local function make_finder()
    return finders.new_table {
      results = gy.list(root),
      entry_maker = function(e)
        return {
          value = e,
          display = ('%-12s %-16s %s'):format(e.gd, e.age, e.title),
          ordinal = e.title,
        }
      end,
    }
  end

  pickers.new({}, {
    prompt_title = ('%s · graveyard'):format(vim.fs.basename(root)),
    finder = make_finder(),
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'buried changes',
      define_preview = function(self, entry)
        vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false,
          vim.split(gy.show(root, entry.value), '\n', { plain = true }))
        vim.bo[self.state.bufnr].filetype = 'diff'
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local t = picker_tools(prompt_bufnr, map, make_finder)
      t.bind('<CR>', 'restore (pop back into worktree)', function()
        local e = t.selected()
        if not e then return end
        actions.close(prompt_bufnr)
        local ok2, err = pcall(gy.pop, root, e)
        if not ok2 then return notify(err, vim.log.levels.ERROR) end
        local st = state.current
        if st and st.parse.root == root then state.refresh(st) end
        refresh_signs()
        vim.cmd('checktime')
        notify('restored from graveyard: ' .. e.title)
      end)
      t.bind('<C-d>', 'delete forever', function()
        local e = t.selected()
        if not e then return end
        if vim.fn.confirm(('Delete "%s" from the graveyard forever?'):format(e.title), '&Yes\n&No', 2) ~= 1 then
          return
        end
        local ok2, err = pcall(gy.drop, root, e)
        if not ok2 then return notify(err, vim.log.levels.ERROR) end
        notify('deleted from graveyard: ' .. e.title)
        t.refresh()
      end)
      return true
    end,
  }):find()
end

function M.pick_runs()
  local ok, root = pcall(diff.root)
  if not ok then return notify(root, vim.log.levels.ERROR) end
  local parse = diff.parse(root)
  state.sync_cache(root, parse)
  local runs = state.runs(root)
  if #runs == 0 then
    return notify('no cached regroup runs for this repo', vim.log.levels.WARN)
  end

  local pickers = require('telescope.pickers')
  local finders = require('telescope.finders')
  local conf = require('telescope.config').values
  local previewers = require('telescope.previewers')
  local actions = require('telescope.actions')

  for _, run in ipairs(runs) do
    local known = {}
    for _, id in ipairs(run.ids) do known[id] = true end
    run.covered = 0
    for _, h in ipairs(parse.hunks) do
      if known[h.id] then run.covered = run.covered + 1 end
    end
  end

  pickers.new({}, {
    prompt_title = ('%s · regroup runs (%d current hunks)'):format(vim.fs.basename(root), #parse.hunks),
    finder = finders.new_table {
      results = runs,
      entry_maker = function(run)
        return {
          value = run,
          display = ('%-30s %d groups  covers %d/%d  %s ago'):format(
            run.key, #run.groups, run.covered, #parse.hunks, rel_age(run.time)),
          ordinal = run.key,
        }
      end,
    },
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'run',
      define_preview = function(self, entry)
        local run = entry.value
        local lines = {}
        for _, g in ipairs(run.groups) do
          local live = 0
          for _, id in ipairs(g.hunks) do
            if parse.by_id[id] then live = live + 1 end
          end
          table.insert(lines, ('%2d/%-2d %s'):format(live, #g.hunks, g.title))
        end
        vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, lines)
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local t = picker_tools(prompt_bufnr, map, nil)
      t.bind('<CR>', 'load run into group picker', function()
        local run = t.selected()
        if not run then return end
        actions.close(prompt_bufnr)
        state.current = { parse = parse, groups = run.groups, config = run.config }
        M.pick_groups()
      end)
      return true
    end,
  }):find()
end

return M
