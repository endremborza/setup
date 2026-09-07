local M = {}

local git = require('regroup.git')
local state = require('regroup.state')
local review = require('regroup.review')
local commit = require('regroup.commit')

local function notify(msg, level)
  vim.notify(msg, level or vim.log.levels.INFO)
end

local refresh_signs = commit.refresh_signs

local function confirm(question, default_no)
  return vim.fn.confirm(question, '&Yes\n&No', default_no and 2 or 1) == 1
end

-- live hunks of a patch, in diff order
local function live_recs(st, p)
  local out = {}
  for _, id in ipairs(p.hunks) do
    local h = st.by_id[id]
    if h then table.insert(out, h) end
  end
  table.sort(out, function(a, b) return a.seq < b.seq end)
  return out
end

local function live_ids(st, p)
  return vim.tbl_map(function(h) return h.id end, live_recs(st, p))
end

-- distinct paths in hunk order, each with the number of hunks it carries
local function files_of(recs)
  local seen, out = {}, {}
  for _, h in ipairs(recs) do
    local f = seen[h.path]
    if f then
      f.n = f.n + 1
    else
      f = { path = h.path, n = 1 }
      seen[h.path] = f
      table.insert(out, f)
    end
  end
  return out
end

local function first_change(h)
  for _, l in ipairs(vim.split(h.text, '\n', { plain = true })) do
    if l:match('^[%+%-]') and not l:match('^[%+%-][%+%-][%+%-] ') then return l end
  end
  return ''
end

-- Hunks no patch of the run covers collect in one synthetic, unpersisted patch.
local function display_patches(st)
  local assigned = {}
  for _, p in ipairs(st.patches) do
    for _, id in ipairs(p.hunks) do assigned[id] = true end
  end
  local stray = {}
  for _, h in ipairs(st.hunks) do
    if not assigned[h.id] then table.insert(stray, h.id) end
  end
  local out = vim.list_slice(st.patches)
  if #stray > 0 then
    table.insert(out, { id = '', title = '(unassigned new changes)', message = '', hunks = stray, stray = true })
  end
  return out
end

local function unassigned(st)
  for _, p in ipairs(display_patches(st)) do
    if p.stray then return #p.hunks end
  end
  return 0
end

-- Every write goes through the engine; the session reloads from its listing afterwards.
local function engine(st, args)
  local res = git.engine(st.root, args)
  if res.code ~= 0 then
    notify('regroup: ' .. git.output(res), vim.log.levels.ERROR)
    return false
  end
  state.refresh(st)
  refresh_signs()
  vim.cmd('checktime')
  return true, vim.trim(res.stdout or '')
end

-- what names a patch to the engine: its id, or the hunk ids of the synthetic one
local function targets(st, p)
  if p.stray then return live_ids(st, p) end
  return { p.id }
end

local function with_targets(st, p, verb)
  local t = targets(st, p)
  if #t == 0 then return notify('patch has no remaining hunks', vim.log.levels.WARN) end
  local ok, out = engine(st, vim.list_extend({ 'patch', verb }, t))
  if ok then notify(('%s: %s'):format(out, p.title)) end
end

function M.stage(st, p) with_targets(st, p, 'stage') end
function M.unstage(st, p) with_targets(st, p, 'unstage') end

function M.discard(st, p)
  local n = #live_recs(st, p)
  if n == 0 then return notify('patch has no remaining hunks', vim.log.levels.WARN) end
  if confirm(('Discard %d hunk(s) of "%s"? This reverts them to HEAD.'):format(n, p.title), true) then
    with_targets(st, p, 'discard')
  end
end

function M.stage_hunk(st, h) engine(st, { 'patch', 'stage', h.id }) end
function M.unstage_hunk(st, h) engine(st, { 'patch', 'unstage', h.id }) end

function M.discard_hunk(st, h)
  if confirm(('Discard %s:%d? This reverts it to HEAD.'):format(h.path, h.new_start), true) then
    engine(st, { 'patch', 'discard', h.id })
  end
end

function M.bury(st, p)
  if p.stray then return notify('place the unassigned hunks first (<C-e> or <C-o>)', vim.log.levels.WARN) end
  local n = #live_recs(st, p)
  if n == 0 then return notify('patch has no remaining hunks', vim.log.levels.WARN) end
  if confirm(('Bury %d hunk(s) of "%s" to the graveyard (git stash)?'):format(n, p.title)) then
    local ok, out = engine(st, { 'patch', 'bury', p.id })
    if ok then notify('⚰ ' .. out) end
  end
end

-- Hand the run back to the engine to place its unassigned hunks, then reopen on the result.
function M.extend_run(root, config)
  notify(('regroup: extending [%s] — placing the unassigned hunks...'):format(state.key(config)))
  git.engine(root, { 'run', '--extend', config.granularity, config.model, config.context }, function(res)
    if res.code ~= 0 then
      return notify('regroup: extend failed\n' .. git.output(res), vim.log.levels.ERROR)
    end
    local st = state.load(root, config)
    if not st then return notify('regroup: run no longer in the cache', vim.log.levels.WARN) end
    local left = unassigned(st)
    notify(('regroup: [%s] updated — %d patches%s'):format(state.key(config), #st.patches,
      left > 0 and (', %d hunk(s) still unassigned'):format(left) or ''))
    M.pick_patches()
  end)
end

function M.goto_hunk(p, idx)
  local st = state.current
  state.refresh(st)
  local live = live_recs(st, p)
  if #live == 0 then
    return notify('patch has no remaining hunks (committed or discarded)', vim.log.levels.WARN)
  end
  idx = ((idx - 1) % #live) + 1
  st.pos = { patch = p, idx = idx }
  local h = live[idx]
  review.base = 'HEAD'
  review.jump(st.root .. '/' .. h.path, h.new_start)
  notify(('[%d/%d] %s'):format(idx, #live, p.title))
end

function M.nav(dir)
  local st = state.current
  if not st or not st.pos then
    return notify('no active patch — run :Regroup', vim.log.levels.WARN)
  end
  M.goto_hunk(st.pos.patch, st.pos.idx + dir)
end

local function same_patch(a, b)
  return a == b or (a and b and a.stray and b.stray) or false
end

function M.nav_patch(dir)
  local st = state.current
  if not st or not st.pos then
    return notify('no active patch — run :Regroup', vim.log.levels.WARN)
  end
  state.refresh(st)
  local live = {}
  for _, p in ipairs(display_patches(st)) do
    if #live_recs(st, p) > 0 then table.insert(live, p) end
  end
  if #live == 0 then
    return notify('no patches with remaining hunks', vim.log.levels.WARN)
  end
  local cur = 1
  for i, p in ipairs(live) do
    if same_patch(p, st.pos.patch) then cur = i end
  end
  M.goto_hunk(live[((cur - 1 + dir) % #live) + 1], 1)
end

function M.reopen()
  local st = state.current
  if not st then
    return notify('no regroup session — run :Regroup', vim.log.levels.WARN)
  end
  M.pick_patches({ select = st.pos and st.pos.patch })
end

-- The message is edited in the shared commit buffer; the engine stages the patch and
-- refuses when the index holds anything else.
function M.commit_patch(p)
  local st = state.current
  if p.stray then return notify('place the unassigned hunks first (<C-e> or <C-o>)', vim.log.levels.WARN) end
  state.refresh(st)
  local live = live_recs(st, p)
  if #live == 0 then return notify('nothing left to commit in this patch', vim.log.levels.WARN) end
  local hunk_lines = {}
  for _, h in ipairs(live) do
    table.insert(hunk_lines, ('#   %s (%s)'):format(h.path, h.id))
  end
  local seed = { p.title, '' }
  vim.list_extend(seed, vim.split(p.message or '', '\n', { plain = true }))
  commit.buffer(seed, hunk_lines, function(msg)
    local ok, out = engine(st, { 'patch', 'commit', p.id, '--message', msg })
    if not ok then error('commit failed', 0) end
    notify('✓ ' .. out)
  end)
end

local function slug(title)
  return title:lower():gsub('[^%w]+', '-'):gsub('^%-+', ''):gsub('%-+$', ''):sub(1, 40)
end

-- A patch branch from the picked patches: committed there in order, the rest stays dirty.
function M.branch_new(st, patches)
  local ids = {}
  for _, p in ipairs(patches) do
    if not p.stray and #live_recs(st, p) > 0 then table.insert(ids, p.id) end
  end
  if #ids == 0 then return notify('pick patches with remaining hunks', vim.log.levels.WARN) end
  vim.ui.input({ prompt = 'patch branch: ', default = slug(patches[1].title) }, function(name)
    if not name or name == '' then return end
    local ok, out = engine(st, vim.list_extend({ 'branch', 'new', name }, ids))
    if ok then notify(out) end
  end)
end

local function land(root, name, after)
  notify(('regroup: landing %s...'):format(name))
  git.engine(root, { 'branch', 'land', name }, function(res)
    if res.code ~= 0 then
      return notify('regroup: land failed\n' .. git.output(res), vim.log.levels.ERROR)
    end
    refresh_signs()
    vim.cmd('checktime')
    notify(vim.trim(res.stdout))
    if after then after() end
  end)
end

function M.land_current(st)
  local name = st.branch
  if name == '' then return notify('detached HEAD', vim.log.levels.WARN) end
  local summary = git.engine(st.root, { 'branch', 'show', name })
  if summary.code ~= 0 or vim.trim(summary.stdout) == '' then
    return notify(('%s has nothing to land'):format(name), vim.log.levels.WARN)
  end
  if confirm(('Land %s as one squashed commit?\n%s'):format(name, vim.trim(summary.stdout))) then
    land(st.root, name, function() state.refresh(st) end)
  end
end

local function patch_preview(st, p, bufnr)
  local lines = { '# ' .. p.title, '' }
  for _, l in ipairs(vim.split(p.message or '', '\n', { plain = true })) do
    table.insert(lines, l)
  end
  local live = live_recs(st, p)
  local files = files_of(live)
  if #files > 1 then  -- one file names itself in every hunk header below
    table.insert(lines, '')
    table.insert(lines, ('# %d hunks in %d files'):format(#live, #files))
    for _, f in ipairs(files) do
      table.insert(lines, ('#  %2d  %s'):format(f.n, f.path))
    end
  end
  if p.mixed and #p.mixed > 0 then
    table.insert(lines, '')
    for _, m in ipairs(p.mixed) do
      table.insert(lines, ('# MIXED %s: %s'):format(m.hunk, m.note))
    end
  end
  for _, h in ipairs(live) do
    table.insert(lines, '')
    table.insert(lines, ('# [%s] %s'):format(h.id, h.path))
    vim.list_extend(lines, vim.split(h.text, '\n', { plain = true }))
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

  -- the multi-selection (<Tab>), or the entry under the cursor
  function tools.picked()
    local p = action_state.get_current_picker(prompt_bufnr)
    local out = {}
    for _, entry in ipairs(p:get_multi_selection()) do table.insert(out, entry.value) end
    if #out == 0 and tools.selected() then out = { tools.selected() } end
    return out
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

local function telescope()
  return require('telescope.pickers'), require('telescope.finders'),
      require('telescope.config').values, require('telescope.previewers'), require('telescope.actions')
end

function M.move_hunk(h, from)
  local st = state.current
  local targets_ = vim.tbl_filter(function(p) return p ~= from end, st.patches)
  if #targets_ == 0 then return notify('no other patch to move into', vim.log.levels.WARN) end
  local pickers, finders, conf, previewers, actions = telescope()
  pickers.new({}, {
    prompt_title = ('move %s:%d →'):format(h.path, h.new_start),
    finder = finders.new_table {
      results = targets_,
      entry_maker = function(p)
        return {
          value = p,
          display = ('%2d hunks  %s'):format(#live_recs(st, p), p.title),
          ordinal = p.title .. ' ' .. (p.message or ''),
        }
      end,
    },
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'patch',
      define_preview = function(self, entry)
        patch_preview(st, entry.value, self.state.bufnr)
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local t = picker_tools(prompt_bufnr, map, nil)
      t.bind('<CR>', 'move hunk here', function()
        local p = t.selected()
        if not p then return end
        actions.close(prompt_bufnr)
        local ok, out = engine(st, { 'patch', 'move', h.id, p.id })
        if ok then notify(out) end
        M.pick_hunks(from)
      end)
      return true
    end,
  }):find()
end

function M.pick_patches(opts)
  opts = opts or {}
  local st = state.current
  if not st then
    return notify('no regroup session — run :Regroup', vim.log.levels.WARN)
  end
  local pickers, finders, conf, previewers, actions = telescope()

  local function entry_maker(p)
    local live = live_recs(st, p)
    local files = files_of(live)
    local n = #live
    local tag
    if n == 0 then
      tag = '· gone'
    elseif p.stray then
      tag = '? new'
    else
      local staged = 0
      for _, h in ipairs(live) do
        if st.staged[h.id] then staged = staged + 1 end
      end
      tag = (staged == n and '● ' or staged > 0 and '◐ ' or '') .. n .. ' hunk' .. (n == 1 and '' or 's')
    end
    local paths = {}
    for _, f in ipairs(files) do table.insert(paths, f.path) end
    return {
      value = p,
      display = ('%-10s %-8s %s'):format(tag,
        n > 0 and (#files .. ' file' .. (#files == 1 and '' or 's')) or '', p.title),
      ordinal = table.concat({ p.title, p.message or '', table.concat(paths, ' ') }, ' '),
    }
  end

  local function make_finder()
    return finders.new_table { results = display_patches(st), entry_maker = entry_maker }
  end

  local select_index
  if opts.select then
    for i, p in ipairs(display_patches(st)) do
      if same_patch(p, opts.select) then select_index = i end
    end
  end

  local function each_picked(t, fn)
    for _, p in ipairs(t.picked()) do fn(p) end
    t.refresh()
  end

  pickers.new({}, {
    prompt_title = ('%s @%s · patches [%s] — ? for keys'):format(
      vim.fs.basename(st.root), st.branch ~= '' and st.branch or 'detached', st.key),
    default_selection_index = select_index,
    finder = make_finder(),
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'patch',
      define_preview = function(self, entry)
        patch_preview(st, entry.value, self.state.bufnr)
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local t = picker_tools(prompt_bufnr, map, make_finder)
      t.bind('<CR>', 'browse patch (then ]g/[g)', function()
        local p = t.selected()
        if not p then return end
        actions.close(prompt_bufnr)
        M.goto_hunk(p, 1)
      end)
      t.bind('<C-h>', 'hunks of patch', function()
        local p = t.selected()
        if not p then return end
        actions.close(prompt_bufnr)
        M.pick_hunks(p)
      end)
      t.bind('<C-s>', 'stage', function() each_picked(t, function(p) M.stage(st, p) end) end)
      t.bind('<C-u>', 'unstage', function() each_picked(t, function(p) M.unstage(st, p) end) end)
      t.bind('<C-d>', 'discard (revert to HEAD)', function() each_picked(t, function(p) M.discard(st, p) end) end)
      t.bind('<C-t>', 'bury (stash to graveyard)', function() each_picked(t, function(p) M.bury(st, p) end) end)
      t.bind('<C-y>', 'commit on the current branch', function()
        local p = t.selected()
        if not p then return end
        actions.close(prompt_bufnr)
        M.commit_patch(p)
      end)
      t.bind('<C-x>', 'new patch branch from the picked patches', function()
        local picked = t.picked()
        if #picked == 0 then return end
        actions.close(prompt_bufnr)
        M.branch_new(st, picked)
      end)
      t.bind('<C-l>', 'land the current branch (squash onto main)', function()
        actions.close(prompt_bufnr)
        M.land_current(st)
      end)
      t.bind('<C-e>', 'extend run (place unassigned hunks)', function()
        actions.close(prompt_bufnr)
        M.extend_run(st.root, st.config)
      end)
      return true
    end,
  }):find()
end

function M.pick_hunks(p)
  local st = state.current
  local pickers, finders, conf, previewers, actions = telescope()

  local function make_results()
    local out = {}
    for i, h in ipairs(live_recs(st, p)) do
      table.insert(out, { i = i, h = h })
    end
    return out
  end

  local function entry_maker(it)
    return {
      value = it,
      display = ('%s %s:%d  %s'):format(
        st.staged[it.h.id] and '●' or ' ', it.h.path, it.h.new_start, first_change(it.h)),
      ordinal = it.h.path .. ' ' .. first_change(it.h),
    }
  end

  local function make_finder()
    return finders.new_table { results = make_results(), entry_maker = entry_maker }
  end

  pickers.new({}, {
    prompt_title = ('%s — <C-g> back'):format(p.title),
    finder = make_finder(),
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'hunk',
      define_preview = function(self, entry)
        vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false,
          vim.split(entry.value.h.text, '\n', { plain = true }))
        vim.bo[self.state.bufnr].filetype = 'diff'
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local t = picker_tools(prompt_bufnr, map, make_finder)
      local function on_hunk(fn)
        return function()
          local it = t.selected()
          if not (it and it.h) then return end
          fn(it)
        end
      end
      t.bind('<CR>', 'jump to hunk', on_hunk(function(it)
        actions.close(prompt_bufnr)
        M.goto_hunk(p, it.i)
      end))
      t.bind('<C-g>', 'back to patches', function()
        actions.close(prompt_bufnr)
        M.pick_patches({ select = p })
      end)
      t.bind('<C-o>', 'move hunk to another patch', on_hunk(function(it)
        actions.close(prompt_bufnr)
        M.move_hunk(it.h, p)
      end))
      t.bind('<C-s>', 'stage hunk', on_hunk(function(it) M.stage_hunk(st, it.h); t.refresh() end))
      t.bind('<C-u>', 'unstage hunk', on_hunk(function(it) M.unstage_hunk(st, it.h); t.refresh() end))
      t.bind('<C-d>', 'discard hunk', on_hunk(function(it) M.discard_hunk(st, it.h); t.refresh() end))
      return true
    end,
  }):find()
end

function M.pick_graveyard()
  local ok, root = pcall(git.root)
  if not ok then return notify(root, vim.log.levels.ERROR) end
  local gy = require('regroup.graveyard')
  if #gy.list(root) == 0 then
    return notify('graveyard is empty (no regroup stashes)', vim.log.levels.INFO)
  end
  local pickers, finders, conf, previewers, actions = telescope()

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

  local function reload()
    local st = state.current
    if st and st.root == root then state.refresh(st) end
    refresh_signs()
    vim.cmd('checktime')
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
        reload()
        notify('restored from graveyard: ' .. e.title)
      end)
      t.bind('<C-d>', 'delete forever', function()
        local e = t.selected()
        if not e then return end
        if not confirm(('Delete "%s" from the graveyard forever?'):format(e.title), true) then return end
        local ok2, err = pcall(gy.drop, root, e)
        if not ok2 then return notify(err, vim.log.levels.ERROR) end
        notify('deleted from graveyard: ' .. e.title)
        t.refresh()
      end)
      return true
    end,
  }):find()
end

function M.pick_runs(ctx)
  local root, data, runs = ctx.root, ctx.data, ctx.runs
  local pickers, finders, conf, previewers, actions = telescope()
  local live = {}
  for _, h in ipairs(data.hunks) do live[h.id] = true end
  for _, run in ipairs(runs) do
    run.covered = 0
    for _, id in ipairs(run.ids) do
      if live[id] then run.covered = run.covered + 1 end
    end
  end

  pickers.new({}, {
    prompt_title = ('%s · regroup runs (%d current hunks) — ? for keys'):format(
      vim.fs.basename(root), #data.hunks),
    finder = finders.new_table {
      results = runs,
      entry_maker = function(run)
        return {
          value = run,
          display = ('%-30s %d patches  covers %d/%d  %s ago'):format(
            run.key, #run.patches, run.covered, #data.hunks, rel_age(run.time)),
          ordinal = run.key,
        }
      end,
    },
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'run',
      define_preview = function(self, entry)
        local lines = {}
        for _, p in ipairs(entry.value.patches) do
          local n = 0
          for _, id in ipairs(p.hunks) do
            if live[id] then n = n + 1 end
          end
          table.insert(lines, ('%2d/%-2d %s'):format(n, #p.hunks, p.title))
        end
        vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, lines)
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local t = picker_tools(prompt_bufnr, map, nil)
      t.bind('<CR>', 'review this run', function()
        local run = t.selected()
        if not run then return end
        actions.close(prompt_bufnr)
        M.open_run(root, run.config)
      end)
      t.bind('<C-e>', 'extend run (place unassigned hunks)', function()
        local run = t.selected()
        if not run then return end
        actions.close(prompt_bufnr)
        M.extend_run(root, run.config)
      end)
      t.bind('<C-t>', 'graveyard', function()
        actions.close(prompt_bufnr)
        M.pick_graveyard()
      end)
      t.bind('<C-x>', 'patch branches', function()
        actions.close(prompt_bufnr)
        M.pick_branches()
      end)
      return true
    end,
  }):find()
end

-- Make the run current for the engine too, so the shell's `hunks patch …` acts on the same one.
function M.open_run(root, config)
  local res = git.engine(root, { 'use', config.granularity, config.model, config.context })
  if res.code ~= 0 then return notify('regroup: ' .. git.output(res), vim.log.levels.ERROR) end
  state.load(root, config)
  M.pick_patches()
end

function M.pick_branches()
  local ok, root = pcall(git.root)
  if not ok then return notify(root, vim.log.levels.ERROR) end
  local pickers, finders, conf, previewers, actions = telescope()

  local function rows()
    local res = git.engine(root, { 'branch', 'show', '--json' })
    if res.code ~= 0 then
      notify('regroup: ' .. git.output(res), vim.log.levels.ERROR)
      return {}
    end
    return vim.json.decode(res.stdout)
  end

  local function make_finder()
    return finders.new_table {
      results = rows(),
      entry_maker = function(b)
        return {
          value = b,
          display = ('%s %-30s %3d commits  %s%s'):format(
            b.current and '*' or ' ', b.name, b.commits, b.stat, b.worktree ~= '' and ('  [' .. b.worktree .. ']') or ''),
          ordinal = b.name,
        }
      end,
    }
  end

  if #rows() == 0 then return notify('no patch branches', vim.log.levels.INFO) end

  pickers.new({}, {
    prompt_title = ('%s · patch branches — ? for keys'):format(vim.fs.basename(root)),
    finder = make_finder(),
    sorter = conf.generic_sorter({}),
    previewer = previewers.new_buffer_previewer {
      title = 'commits ahead',
      define_preview = function(self, entry)
        local res = git.engine(root, { 'branch', 'show', entry.value.name })
        vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false,
          vim.split(vim.trim(res.stdout or ''), '\n', { plain = true }))
      end,
    },
    attach_mappings = function(prompt_bufnr, map)
      local t = picker_tools(prompt_bufnr, map, make_finder)
      t.bind('<CR>', 'switch to branch', function()
        local b = t.selected()
        if not b then return end
        actions.close(prompt_bufnr)
        local res = git.git(root, { 'switch', b.name })
        if res.code ~= 0 then return notify(git.output(res), vim.log.levels.ERROR) end
        vim.cmd('checktime')
        notify('on ' .. b.name)
      end)
      t.bind('<C-l>', 'land (squash onto main)', function()
        local b = t.selected()
        if not b then return end
        actions.close(prompt_bufnr)
        if confirm(('Land %s as one squashed commit?'):format(b.name)) then
          land(root, b.name, function()
            local st = state.current
            if st and st.root == root then state.refresh(st) end
          end)
        end
      end)
      t.bind('<C-d>', 'drop (archive under refs/dropped)', function()
        local b = t.selected()
        if not b then return end
        if not confirm(('Drop %s without landing?'):format(b.name), true) then return end
        local res = git.engine(root, { 'branch', 'drop', b.name })
        if res.code ~= 0 then return notify(git.output(res), vim.log.levels.ERROR) end
        notify(vim.trim(res.stdout))
        t.refresh()
      end)
      return true
    end,
  }):find()
end

return M
