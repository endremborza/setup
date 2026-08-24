local M = {}

-- The engine and its AI config live in dienpy: nvim reads cached runs, extends the one
-- it is looking at (`state.extend`), and never composes an analysis config of its own.
local ENGINE_CMD = 'dienpy hunks run'

local function yank_engine_cmd(root, msg)
  pcall(vim.fn.setreg, '+', ENGINE_CMD)
  pcall(vim.fn.setreg, '"', ENGINE_CMD)
  vim.notify(('regroup: %s in %s\nrun in a shell there (yanked):  %s')
    :format(msg, vim.fs.basename(root), ENGINE_CMD), vim.log.levels.WARN)
end

-- Tokens are matched against the parts of a cached run key, so the vocabulary comes
-- from the cache rather than from a copy of dienpy's dimensions.
local function matching(runs, tokens)
  if #tokens == 0 then return runs end
  return vim.tbl_filter(function(run)
    local parts = vim.split(run.key, '|', { plain = true })
    for _, tok in ipairs(tokens) do
      if not vim.tbl_contains(parts, tok) then return false end
    end
    return true
  end, runs)
end

local function context(tokens)
  local diff = require('regroup.diff')
  local state = require('regroup.state')

  local ok, root = pcall(diff.root)
  if not ok then return vim.notify(root, vim.log.levels.ERROR) end
  local parse = diff.parse(root)
  if #parse.hunks == 0 then
    return vim.notify('no uncommitted changes in ' .. vim.fs.basename(root), vim.log.levels.INFO)
  end
  state.sync_cache(root, parse)

  local all = state.runs(root)
  if #all == 0 then return yank_engine_cmd(root, 'no cached analysis') end
  local runs = matching(all, tokens)
  if #runs == 0 then
    return yank_engine_cmd(root, ('no cached run matching %s'):format(table.concat(tokens, ' ')))
  end
  return { root = root, parse = parse, runs = runs }
end

-- Group picker for the run the tokens name; the last-used run when they name several.
function M.open(tokens)
  local state = require('regroup.state')
  local ui = require('regroup.ui')

  local ctx = context(tokens or {})
  if not ctx then return end
  local runs = ctx.runs
  if #runs > 1 then
    local last = state.last_config(ctx.root)
    for _, run in ipairs(runs) do
      if last and state.key(run.config) == state.key(last) then runs = { run } end
    end
  end
  if #runs > 1 then return ui.pick_runs(ctx) end
  state.load(ctx.root, ctx.parse, runs[1].config)
  ui.pick_groups()
end

function M.runs(tokens)
  local ctx = context(tokens or {})
  if ctx then require('regroup.ui').pick_runs(ctx) end
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

function M.setup()
  ensure_helptags()

  vim.api.nvim_create_user_command('Regroup', function(cmd)
    M.open(cmd.fargs)
  end, {
    nargs = '*',
    complete = function(arglead)
      local ok, root = pcall(require('regroup.diff').root)
      if not ok then return {} end
      local seen, out = {}, {}
      for _, run in ipairs(require('regroup.state').runs(root)) do
        for _, part in ipairs(vim.split(run.key, '|', { plain = true })) do
          if not seen[part] and part:find(arglead, 1, true) == 1 then
            seen[part] = true
            table.insert(out, part)
          end
        end
      end
      return out
    end,
  })

  vim.api.nvim_create_user_command('RegroupRuns', function(cmd)
    M.runs(cmd.fargs)
  end, { nargs = '*' })

  vim.api.nvim_create_user_command('RegroupGraveyard', function()
    require('regroup.ui').pick_graveyard()
  end, {})

  vim.keymap.set('n', '<leader>gg', function()
    local state = require('regroup.state')
    local ok, root = pcall(require('regroup.diff').root)
    if state.current and ok and state.current.parse.root == root then
      return require('regroup.ui').reopen()
    end
    M.open {}
  end, { desc = '[G]it change [G]roups (picker, or run list when no session)' })
  vim.keymap.set('n', '<leader>gG', function() M.runs {} end, { desc = '[G]it change [G]roup runs' })
  vim.keymap.set('n', ']g', function() require('regroup.ui').nav(1) end, { desc = 'Next hunk in change group' })
  vim.keymap.set('n', '[g', function() require('regroup.ui').nav(-1) end, { desc = 'Prev hunk in change group' })
  vim.keymap.set('n', ']G', function() require('regroup.ui').nav_group(1) end, { desc = 'Next change group' })
  vim.keymap.set('n', '[G', function() require('regroup.ui').nav_group(-1) end, { desc = 'Prev change group' })
end

return M
