local M = {}

M.opts = {
  models = { 'haiku', 'sonnet', 'opus', 'fable' },
  default = { granularity = 'normal', model = 'sonnet', context = 'bare' },
}

local GRANULARITIES = { loose = true, normal = true, granular = true }
local CONTEXTS = { bare = true, agents = true, explore = true }

local function dim_values()
  return {
    granularity = { 'loose', 'normal', 'granular' },
    model = M.opts.models,
    context = { 'bare', 'agents', 'explore' },
  }
end

function M.classify_args(fargs)
  local cfg = {}
  for _, a in ipairs(fargs) do
    if GRANULARITIES[a] then
      cfg.granularity = a
    elseif CONTEXTS[a] then
      cfg.context = a
    else
      cfg.model = a
    end
  end
  return cfg
end

local function engine_cmd(config, force)
  return ('dienpy hunks run %s %s %s%s'):format(
    config.granularity, config.context, config.model, force and ' --force' or '')
end

function M.proceed(root, parse, config, force)
  local state = require('regroup.state')
  local ui = require('regroup.ui')
  state.touch_last(root, config)
  if not force then
    local st = state.current
    if st and st.parse.root == root and state.key(st.config) == state.key(config) then
      st.parse = parse
      state.reconcile(st)
      return ui.pick_groups()
    end
    local cached = state.load_cache(root, parse, config)
    if cached then
      state.current = { parse = parse, groups = cached, config = config }
      return ui.pick_groups()
    end
  end
  local cmd = engine_cmd(config, force)
  pcall(vim.fn.setreg, '+', cmd)
  pcall(vim.fn.setreg, '"', cmd)
  vim.notify(('regroup: no current analysis for [%s] in %s\nrun in a shell there (yanked):  %s')
    :format(state.key(config), vim.fs.basename(root), cmd), vim.log.levels.WARN)
end

function M.run(opts)
  opts = opts or {}
  local diff = require('regroup.diff')
  local state = require('regroup.state')

  local ok, root = pcall(diff.root)
  if not ok then return vim.notify(root, vim.log.levels.ERROR) end
  local parse = diff.parse(root)
  if #parse.hunks == 0 then
    return vim.notify('no uncommitted changes in ' .. vim.fs.basename(root), vim.log.levels.INFO)
  end
  state.sync_cache(root, parse)

  local initial = vim.tbl_extend('force',
    M.opts.default,
    state.last_config(root) or {},
    (state.current and state.current.parse.root == root and state.current.config) or {},
    opts.config or {})

  if opts.config then
    return M.proceed(root, parse, initial, opts.force)
  end

  require('regroup.menu').open {
    values = dim_values(),
    initial = initial,
    title = (' regroup · %s '):format(vim.fs.basename(root)),
    info = function(cfg)
      local st = state.current
      if st and st.parse.root == root and state.key(st.config) == state.key(cfg) then
        return ('%d hunks · cached ✓ instant'):format(#parse.hunks)
      end
      local entry = state.entry(root, cfg)
      if not entry then
        return ('%d hunks · not cached — ⏎ yanks engine cmd'):format(#parse.hunks)
      end
      local known = {}
      for _, id in ipairs(entry.ids) do known[id] = true end
      local new = 0
      for _, h in ipairs(parse.hunks) do
        if not known[h.id] then new = new + 1 end
      end
      if new == 0 then
        return ('%d hunks · cached ✓ instant'):format(#parse.hunks)
      end
      return ('%d hunks · +%d new — ⏎ yanks engine cmd'):format(#parse.hunks, new)
    end,
    on_confirm = function(cfg, force)
      M.proceed(root, parse, cfg, force or opts.force)
    end,
    on_runs = function()
      require('regroup.ui').pick_runs()
    end,
    on_graveyard = function()
      require('regroup.ui').pick_graveyard()
    end,
  }
end

local function ensure_helptags()
  local doc = vim.fn.stdpath('config') .. '/doc'
  local txt = vim.uv.fs_stat(doc .. '/regroup.txt')
  if not txt then return end
  local tags = vim.uv.fs_stat(doc .. '/tags')
  if not tags or tags.mtime.sec < txt.mtime.sec then
    pcall(vim.cmd, 'helptags ' .. vim.fn.fnameescape(doc))
  end
end

function M.setup(opts)
  M.opts = vim.tbl_deep_extend('force', M.opts, opts or {})
  ensure_helptags()

  vim.api.nvim_create_user_command('Regroup', function(cmd)
    local cfg = M.classify_args(cmd.fargs)
    M.run {
      config = next(cfg) ~= nil and cfg or nil,
      force = cmd.bang,
    }
  end, {
    nargs = '*',
    bang = true,
    complete = function()
      local vals = { 'loose', 'normal', 'granular', 'bare', 'agents', 'explore' }
      return vim.list_extend(vals, M.opts.models)
    end,
  })

  vim.api.nvim_create_user_command('RegroupRuns', function()
    require('regroup.ui').pick_runs()
  end, {})

  vim.api.nvim_create_user_command('RegroupGraveyard', function()
    require('regroup.ui').pick_graveyard()
  end, {})

  vim.keymap.set('n', '<leader>gg', function()
    local state = require('regroup.state')
    local ok, root = pcall(require('regroup.diff').root)
    if state.current and ok and state.current.parse.root == root then
      return require('regroup.ui').reopen()
    end
    M.run {}
  end, { desc = '[G]it change [G]roups (picker, or config menu when no session)' })
  vim.keymap.set('n', '<leader>gG', function() require('regroup.ui').pick_runs() end,
    { desc = '[G]it change [G]roup runs' })
  vim.keymap.set('n', ']g', function() require('regroup.ui').nav(1) end, { desc = 'Next hunk in change group' })
  vim.keymap.set('n', '[g', function() require('regroup.ui').nav(-1) end, { desc = 'Prev hunk in change group' })
  vim.keymap.set('n', ']G', function() require('regroup.ui').nav_group(1) end, { desc = 'Next change group' })
  vim.keymap.set('n', '[G', function() require('regroup.ui').nav_group(-1) end, { desc = 'Prev change group' })
end

return M
