local M = {}

M.opts = { model = 'sonnet', granularity = 'normal' }

function M.run(opts)
  opts = opts or {}
  local diff = require('regroup.diff')
  local state = require('regroup.state')
  local ai = require('regroup.ai')
  local ui = require('regroup.ui')

  local granularity = opts.granularity
      or (state.current and state.current.granularity)
      or M.opts.granularity
  if not ai.granularities[granularity] then
    return vim.notify('regroup: unknown granularity ' .. granularity, vim.log.levels.ERROR)
  end

  local ok, root = pcall(diff.root)
  if not ok then return vim.notify(root, vim.log.levels.ERROR) end
  local parse = diff.parse(root)
  if #parse.hunks == 0 then
    return vim.notify('no uncommitted changes', vim.log.levels.INFO)
  end

  if not opts.force then
    local st = state.current
    if st and st.parse.root == root and st.granularity == granularity then
      st.parse = parse
      return ui.pick_groups()
    end
    local cached = state.load_cache(root, parse, granularity)
    if cached then
      state.current = { parse = parse, groups = cached, granularity = granularity }
      vim.notify('regroup: reusing cached analysis')
      return ui.pick_groups()
    end
  end

  vim.notify(('regroup: analyzing %d hunks (%s, %s)...'):format(#parse.hunks, granularity, M.opts.model))
  ai.analyze(parse, { granularity = granularity, model = M.opts.model }, function(groups, err)
    if not groups then
      return vim.notify('regroup: ' .. err, vim.log.levels.ERROR)
    end
    state.current = { parse = parse, groups = groups, granularity = granularity }
    state.save_cache(state.current)
    ui.pick_groups()
  end)
end

function M.setup(opts)
  M.opts = vim.tbl_extend('force', M.opts, opts or {})

  vim.api.nvim_create_user_command('Regroup', function(cmd)
    M.run { granularity = cmd.fargs[1], force = cmd.bang }
  end, {
    nargs = '?',
    bang = true,
    complete = function() return { 'loose', 'normal', 'granular' } end,
  })

  vim.keymap.set('n', '<leader>gg', function() M.run {} end, { desc = '[G]it change [G]roups' })
  vim.keymap.set('n', ']g', function() require('regroup.ui').nav(1) end, { desc = 'Next hunk in change group' })
  vim.keymap.set('n', '[g', function() require('regroup.ui').nav(-1) end, { desc = 'Prev hunk in change group' })
end

return M
