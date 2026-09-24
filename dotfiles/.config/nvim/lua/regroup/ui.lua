local M = {}

local git = require('regroup.git')
local state = require('regroup.state')
local review = require('regroup.review')
local commit = require('regroup.commit')
local picker = require('regroup.picker')

local notify = state.notify
local WARN, ERROR = vim.log.levels.WARN, vim.log.levels.ERROR

local pick_patches, pick_hunks, move_hunk

local function confirm(question, default_no)
  return vim.fn.confirm(question, '&Yes\n&No', default_no and 2 or 1) == 1
end

local function no_session()
  return notify('no regroup session — run :Regroup', WARN)
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

-- what names a patch to the engine: its id, or the hunk ids of the synthetic one
local function targets(p)
  if p.stray then return vim.tbl_map(function(h) return h.id end, p.live) end
  return { p.id }
end

-- An engine write on the run the session shows; the session and buffers reload after it.
local function write(st, args)
  local pointed, err = state.point(st)
  if not pointed then
    notify('regroup: ' .. err, ERROR)
    return false
  end
  local res = git.engine(st.root, args)
  if res.code ~= 0 then
    notify('regroup: ' .. git.output(res), ERROR)
    return false
  end
  return true, vim.trim(res.stdout or '')
end

local function engine(st, args)
  local ok, out = write(st, args)
  if ok then state.after_write(st.root) end
  return ok, out
end

-- one engine call for every picked patch
local function act(st, patches, verb)
  local t = {}
  for _, p in ipairs(patches) do vim.list_extend(t, targets(p)) end
  if #t == 0 then return notify('no remaining hunks', WARN) end
  local ok, out = engine(st, vim.list_extend({ 'patch', verb }, t))
  if ok then notify(out) end
end

local function live_count(patches)
  local n = 0
  for _, p in ipairs(patches) do n = n + #p.live end
  return n
end

local function of_patches(patches)
  if #patches == 1 then return ('"%s"'):format(patches[1].title) end
  return ('%d patches'):format(#patches)
end

local function discard(st, patches)
  local n = live_count(patches)
  if n == 0 then return notify('no remaining hunks', WARN) end
  if confirm(('Discard %d hunk(s) of %s? This reverts them to HEAD.'):format(n, of_patches(patches)), true) then
    act(st, patches, 'discard')
  end
end

-- bury takes one patch per call: each stash carries that patch's title
local function bury(st, patches)
  for _, p in ipairs(patches) do
    if p.stray then return notify('place the unassigned hunks first (<C-e> or <C-o>)', WARN) end
  end
  local ready = vim.tbl_filter(function(p) return #p.live > 0 end, patches)
  if #ready == 0 then return notify('no remaining hunks', WARN) end
  if not confirm(('Bury %d hunk(s) of %s to the graveyard (git stash)?'):format(live_count(ready), of_patches(ready))) then
    return
  end
  for _, p in ipairs(ready) do
    local ok, out = write(st, { 'patch', 'bury', p.id })
    if not ok then break end
    notify('⚰ ' .. out)
  end
  state.after_write(st.root)
end

-- Hand the run to the engine to place its unassigned hunks; the session reloads when done.
local function extend_run(root, config)
  local key = state.key(config)
  notify(('regroup: extending [%s] — placing the unassigned hunks...'):format(key))
  git.engine(root, { 'run', '--extend', config.granularity, config.model, config.context }, function(res)
    if res.code ~= 0 then
      return notify('regroup: extend failed\n' .. git.output(res), ERROR)
    end
    local ok, st = pcall(state.load, root, config)
    if not ok then return notify('regroup: ' .. tostring(st), ERROR) end
    if not st then return notify('regroup: run no longer in the cache', WARN) end
    local left = #st.stray.live
    notify(('regroup: [%s] updated — %d patches%s; <leader>gg reopens'):format(key, #st.patches,
      left > 0 and (', %d hunk(s) still unassigned'):format(left) or ''))
  end)
end

local function goto_hunk(p, idx)
  local st = state.current
  local live = p.live
  if #live == 0 then
    return notify('patch has no remaining hunks (committed or discarded)', WARN)
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
  if not st or not st.pos then return notify('no active patch — run :Regroup', WARN) end
  goto_hunk(st.pos.patch, st.pos.idx + dir)
end

function M.nav_patch(dir)
  local st = state.current
  if not st or not st.pos then return notify('no active patch — run :Regroup', WARN) end
  state.refresh(st)
  local live = vim.tbl_filter(function(p) return #p.live > 0 end, st.shown)
  if #live == 0 then return notify('no patches with remaining hunks', WARN) end
  local cur = 1
  for i, p in ipairs(live) do
    if p == st.pos.patch then cur = i end
  end
  goto_hunk(live[((cur - 1 + dir) % #live) + 1], 1)
end

function M.reopen()
  local st = state.current
  if not st then return no_session() end
  state.refresh(st)
  pick_patches({ select = st.pos and st.pos.patch })
end

-- The message is edited in the shared commit buffer; the engine stages the patch and
-- refuses when the index holds anything else.
local function commit_patch(p)
  local st = state.current
  if p.stray then return notify('place the unassigned hunks first (<C-e> or <C-o>)', WARN) end
  state.refresh(st)
  if #p.live == 0 then return notify('nothing left to commit in this patch', WARN) end
  local hunk_lines = {}
  for _, h in ipairs(p.live) do
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
local function branch_new(st, patches)
  local ids = {}
  for _, p in ipairs(patches) do
    if not p.stray and #p.live > 0 then table.insert(ids, p.id) end
  end
  if #ids == 0 then return notify('pick patches with remaining hunks', WARN) end
  vim.ui.input({ prompt = 'patch branch: ', default = slug(patches[1].title) }, function(name)
    if not name or name == '' then return end
    local ok, out = engine(st, vim.list_extend({ 'branch', 'new', name }, ids))
    if ok then notify(out) end
  end)
end

local function land(root, name)
  notify(('regroup: landing %s...'):format(name))
  git.engine(root, { 'branch', 'land', name }, function(res)
    if res.code ~= 0 then
      return notify('regroup: land failed\n' .. git.output(res), ERROR)
    end
    state.after_write(root)
    notify(vim.trim(res.stdout))
  end)
end

local function land_current(st)
  local name = st.branch
  if name == '' then return notify('detached HEAD', WARN) end
  local summary = git.engine(st.root, { 'branch', 'show', name })
  if summary.code ~= 0 or vim.trim(summary.stdout) == '' then
    return notify(('%s has nothing to land'):format(name), WARN)
  end
  if confirm(('Land %s as one squashed commit?\n%s'):format(name, vim.trim(summary.stdout))) then
    land(st.root, name)
  end
end

local function patch_lines(p)
  local lines = { '# ' .. p.title, '' }
  for _, l in ipairs(vim.split(p.message or '', '\n', { plain = true })) do
    table.insert(lines, l)
  end
  local files = files_of(p.live)
  if #files > 1 then -- one file names itself in every hunk header below
    table.insert(lines, '')
    table.insert(lines, ('# %d hunks in %d files'):format(#p.live, #files))
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
  for _, h in ipairs(p.live) do
    table.insert(lines, '')
    table.insert(lines, ('# [%s] %s'):format(h.id, h.path))
    vim.list_extend(lines, vim.split(h.text, '\n', { plain = true }))
  end
  return lines
end

local function rel_age(t)
  if not t then return '?' end
  local d = os.time() - t
  if d < 90 then return d .. 's' end
  if d < 5400 then return math.floor(d / 60 + 0.5) .. 'm' end
  if d < 129600 then return math.floor(d / 3600 + 0.5) .. 'h' end
  return math.floor(d / 86400 + 0.5) .. 'd'
end

function move_hunk(h, from)
  local st = state.current
  local targets_ = vim.tbl_filter(function(p) return p ~= from end, st.patches)
  if #targets_ == 0 then return notify('no other patch to move into', WARN) end
  picker.open {
    title = ('move %s:%d →'):format(h.path, h.new_start),
    results = function() return targets_ end,
    entry = function(p)
      return { display = ('%2d hunks  %s'):format(#p.live, p.title), ordinal = p.title .. ' ' .. (p.message or '') }
    end,
    preview = patch_lines, preview_ft = 'diff', preview_title = 'patch',
    keys = {
      { '<CR>', 'move hunk here', function(p)
        local ok, out = engine(st, { 'patch', 'move', h.id, p.id })
        if ok then notify(out) end
        pick_hunks(from)
      end, close = true },
    },
  }
end

local function patch_entry(st)
  return function(p)
    local n = #p.live
    local files = files_of(p.live)
    local tag
    if n == 0 then
      tag = '· gone'
    elseif p.stray then
      tag = '? new'
    else
      local staged = 0
      for _, h in ipairs(p.live) do
        if st.staged[h.id] then staged = staged + 1 end
      end
      tag = (staged == n and '● ' or staged > 0 and '◐ ' or '') .. n .. ' hunk' .. (n == 1 and '' or 's')
    end
    local paths = vim.tbl_map(function(f) return f.path end, files)
    return {
      display = ('%-10s %-8s %s'):format(tag,
        n > 0 and (#files .. ' file' .. (#files == 1 and '' or 's')) or '', p.title),
      ordinal = table.concat({ p.title, p.message or '', table.concat(paths, ' ') }, ' '),
    }
  end
end

function pick_patches(opts)
  opts = opts or {}
  local st = state.current
  if not st then return no_session() end
  local select_index
  if opts.select then
    for i, p in ipairs(st.shown) do
      if p == opts.select then select_index = i end
    end
  end
  local function then_refresh(fn)
    return function(v, t)
      fn(v)
      t.refresh()
    end
  end
  picker.open {
    title = ('%s @%s · patches [%s] — ? for keys'):format(
      vim.fs.basename(st.root), st.branch ~= '' and st.branch or 'detached', st.key),
    default_index = select_index,
    results = function() return st.shown end,
    entry = patch_entry(st),
    preview = patch_lines, preview_ft = 'diff', preview_title = 'patch',
    keys = {
      { '<CR>', 'browse patch (then ]g/[g)', function(p) goto_hunk(p, 1) end, close = true },
      { '<C-h>', 'hunks of patch', pick_hunks, close = true },
      { '<C-s>', 'stage', then_refresh(function(ps) act(st, ps, 'stage') end), picked = true },
      { '<C-u>', 'unstage', then_refresh(function(ps) act(st, ps, 'unstage') end), picked = true },
      { '<C-d>', 'discard (revert to HEAD)', then_refresh(function(ps) discard(st, ps) end), picked = true },
      { '<C-t>', 'bury (stash to graveyard)', then_refresh(function(ps) bury(st, ps) end), picked = true },
      { '<C-y>', 'commit on the current branch', commit_patch, close = true },
      { '<C-x>', 'new patch branch from the picked patches', function(ps) branch_new(st, ps) end, picked = true, close = true },
      { '<C-l>', 'land the current branch (squash onto main)', function() land_current(st) end, any = true, close = true },
      { '<C-e>', 'extend run (place unassigned hunks)', function() extend_run(st.root, st.config) end, any = true, close = true },
    },
  }
end

function pick_hunks(p)
  local st = state.current
  local function hunk_action(verb)
    return function(it, t)
      if verb == 'discard'
          and not confirm(('Discard %s:%d? This reverts it to HEAD.'):format(it.h.path, it.h.new_start), true) then
        return
      end
      engine(st, { 'patch', verb, it.h.id })
      t.refresh()
    end
  end
  picker.open {
    title = ('%s — <C-g> back'):format(p.title),
    results = function()
      local out = {}
      for i, h in ipairs(p.live) do out[i] = { i = i, h = h } end
      return out
    end,
    entry = function(it)
      return {
        display = ('%s %s:%d  %s'):format(
          st.staged[it.h.id] and '●' or ' ', it.h.path, it.h.new_start, first_change(it.h)),
        ordinal = it.h.path .. ' ' .. first_change(it.h),
      }
    end,
    preview = function(it) return vim.split(it.h.text, '\n', { plain = true }) end,
    preview_ft = 'diff', preview_title = 'hunk',
    keys = {
      { '<CR>', 'jump to hunk', function(it) goto_hunk(p, it.i) end, close = true },
      { '<C-g>', 'back to patches', function() pick_patches({ select = p }) end, any = true, close = true },
      { '<C-o>', 'move hunk to another patch', function(it) move_hunk(it.h, p) end, close = true },
      { '<C-s>', 'stage hunk', hunk_action('stage') },
      { '<C-u>', 'unstage hunk', hunk_action('unstage') },
      { '<C-d>', 'discard hunk', hunk_action('discard') },
    },
  }
end

-- buried patches: the engine's stashes, addressed by commit hash
function M.pick_graveyard()
  local root = git.try_root()
  if not root then return end
  local function entries()
    local res = git.engine(root, { 'graveyard', 'list', '--json' })
    if res.code ~= 0 then
      notify('regroup: ' .. git.output(res), ERROR)
      return {}
    end
    return state.decode(res.stdout)
  end
  local function restore(e)
    local res = git.engine(root, { 'graveyard', 'restore', e.hash })
    if res.code ~= 0 then return notify('regroup: ' .. git.output(res), ERROR) end
    state.after_write(root)
    notify('restored from graveyard: ' .. e.title)
  end
  picker.open {
    title = ('%s · graveyard'):format(vim.fs.basename(root)),
    empty = 'graveyard is empty (no regroup stashes)',
    results = entries,
    entry = function(e)
      return { display = ('%-12s %-16s %s'):format(e.ref, e.age, e.title), ordinal = e.title }
    end,
    preview = function(e)
      local res = git.git(root, { 'stash', 'show', '-p', e.hash })
      return vim.split(res.code == 0 and res.stdout or git.output(res), '\n', { plain = true })
    end,
    preview_ft = 'diff', preview_title = 'buried changes',
    keys = {
      { '<CR>', 'restore (pop back into worktree)', restore, close = true },
      { '<C-d>', 'delete forever', function(e, t)
        if not confirm(('Delete "%s" from the graveyard forever?'):format(e.title), true) then return end
        local res = git.engine(root, { 'graveyard', 'drop', e.hash })
        if res.code ~= 0 then return notify('regroup: ' .. git.output(res), ERROR) end
        notify('deleted from graveyard: ' .. e.title)
        t.refresh()
      end },
    },
  }
end

function M.pick_runs(ctx)
  local root, data, runs = ctx.root, ctx.data, ctx.runs
  local live = {}
  for _, h in ipairs(data.hunks) do live[h.id] = true end
  for _, run in ipairs(runs) do
    run.covered = 0
    for _, id in ipairs(run.ids) do
      if live[id] then run.covered = run.covered + 1 end
    end
  end
  picker.open {
    title = ('%s · regroup runs (%d current hunks) — ? for keys'):format(vim.fs.basename(root), #data.hunks),
    results = function() return runs end,
    entry = function(run)
      return {
        display = ('%-30s %d patches  covers %d/%d  %s ago'):format(
          run.key, #run.patches, run.covered, #data.hunks, rel_age(run.time)),
        ordinal = run.key,
      }
    end,
    preview = function(run)
      local lines = {}
      for _, p in ipairs(run.patches) do
        local n = 0
        for _, id in ipairs(p.hunks) do
          if live[id] then n = n + 1 end
        end
        table.insert(lines, ('%2d/%-2d %s'):format(n, #p.hunks, p.title))
      end
      return lines
    end,
    preview_title = 'run',
    keys = {
      { '<CR>', 'review this run', function(run) M.open_run(root, run.config) end, close = true },
      { '<C-e>', 'extend run (place unassigned hunks)', function(run) extend_run(root, run.config) end, close = true },
      { '<C-t>', 'graveyard', M.pick_graveyard, any = true, close = true },
      { '<C-x>', 'patch branches', function() M.pick_branches() end, any = true, close = true },
    },
  }
end

-- Open a run's patch picker from `data` (a listing already fetched) or a fresh one; the
-- engine is pointed at the run when it is showing another.
function M.open_run(root, config, data)
  local ok, st = pcall(state.load, root, config, data)
  if not ok then return notify('regroup: ' .. tostring(st), ERROR) end
  if not st then return notify('regroup: run no longer in the cache', WARN) end
  local pointed, err = state.point(st)
  if not pointed then return notify('regroup: ' .. err, ERROR) end
  pick_patches()
end

function M.pick_branches()
  local root = git.try_root()
  if not root then return end
  local function rows()
    local res = git.engine(root, { 'branch', 'show', '--json' })
    if res.code ~= 0 then
      notify('regroup: ' .. git.output(res), ERROR)
      return {}
    end
    return state.decode(res.stdout)
  end
  picker.open {
    title = ('%s · patch branches — ? for keys'):format(vim.fs.basename(root)),
    empty = 'no patch branches',
    results = rows,
    entry = function(b)
      return {
        display = ('%s %-30s %3d commits  %s%s'):format(
          b.current and '*' or ' ', b.name, b.commits, b.stat, b.worktree ~= '' and ('  [' .. b.worktree .. ']') or ''),
        ordinal = b.name,
      }
    end,
    preview = function(b)
      if b.commits == 0 then return {} end
      local res = git.git(root, { 'log', '--oneline', '--no-decorate', '-n', tostring(b.commits), b.name })
      return vim.split(vim.trim(res.stdout or ''), '\n', { plain = true })
    end,
    preview_title = 'commits ahead',
    keys = {
      { '<CR>', 'switch to branch', function(b)
        local res = git.engine(root, { 'branch', 'checkout', b.name })
        if res.code ~= 0 then return notify('regroup: ' .. git.output(res), ERROR) end
        state.after_write(root)
        notify('on ' .. b.name)
      end, close = true },
      { '<C-l>', 'land (squash onto main)', function(b)
        if confirm(('Land %s as one squashed commit?'):format(b.name)) then land(root, b.name) end
      end, close = true },
      { '<C-d>', 'drop (archive under refs/dropped)', function(b, t)
        if not confirm(('Drop %s without landing?'):format(b.name), true) then return end
        local res = git.engine(root, { 'branch', 'drop', b.name })
        if res.code ~= 0 then return notify('regroup: ' .. git.output(res), ERROR) end
        notify(vim.trim(res.stdout))
        t.refresh()
      end },
    },
  }
end

return M
