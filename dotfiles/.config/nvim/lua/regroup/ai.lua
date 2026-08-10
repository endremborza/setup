local M = {}

M.granularities = {
  loose = 'broad thematic groups; a feature together with its tests, docs and mechanical fallout is one group',
  normal =
  'conventional atomic commits; independent concerns are separate groups, mechanical fallout stays with the change that caused it',
  granular =
  'smallest self-consistent units; separate refactoring from behavior changes, separate independent tweaks even within one file',
}

local SCHEMA = vim.json.encode({
  type = 'object',
  properties = {
    groups = {
      type = 'array',
      items = {
        type = 'object',
        properties = {
          title = { type = 'string' },
          message = { type = 'string' },
          hunks = { type = 'array', items = { type = 'string' } },
          mixed = {
            type = 'array',
            items = {
              type = 'object',
              properties = {
                hunk = { type = 'string' },
                note = { type = 'string' },
              },
              required = { 'hunk', 'note' },
            },
          },
        },
        required = { 'title', 'message', 'hunks' },
      },
    },
  },
  required = { 'groups' },
})

local function build_prompt(parse, granularity, feedback)
  local diff = require('regroup.diff')
  local log = vim.system({ 'git', 'log', '--format=%s', '-15' }, { text = true, cwd = parse.root }):wait()
  local parts = {
    'Group these git hunks into change groups (future commits).',
    '',
    'Rules:',
    '- Every hunk id below appears in exactly one group\'s "hunks" array; never dropped, never duplicated.',
    '- Group by semantic concern, not by file: hunks from one file can belong to different groups.',
    '- If a single hunk mixes two distinct concerns, assign it to the dominant one and record it in that group\'s "mixed" array with a note naming the foreign part.',
    '- "title": a commit subject line (<= 72 chars) in the style of the recent subjects below.',
    '- "message": the commit body, what changed and why; do not restate the title.',
    '- Order groups so foundational changes come before things built on them.',
    '',
    ('Granularity "%s": %s.'):format(granularity, M.granularities[granularity]),
    '',
    'Recent commit subjects for style:',
    vim.trim(log.stdout or ''),
    '',
    'Hunks:',
  }
  for _, h in ipairs(parse.hunks) do
    table.insert(parts, '')
    table.insert(parts, ('[%s] %s'):format(h.id, h.path))
    table.insert(parts, diff.hunk_text(h))
  end
  if feedback then
    table.insert(parts, '')
    table.insert(parts, feedback)
  end
  return table.concat(parts, '\n')
end

local function validate(parse, groups)
  local assigned, problems = {}, {}
  for gi, g in ipairs(groups) do
    if g.mixed == vim.NIL then g.mixed = nil end
    for _, id in ipairs(g.hunks) do
      if not parse.by_id[id] then
        table.insert(problems, ('group %d references unknown id %s'):format(gi, id))
      elseif assigned[id] then
        table.insert(problems, ('id %s appears in more than one group'):format(id))
      end
      assigned[id] = true
    end
  end
  for _, h in ipairs(parse.hunks) do
    if not assigned[h.id] then
      table.insert(problems, ('id %s (%s) is not in any group'):format(h.id, h.path))
    end
  end
  return #problems > 0 and table.concat(problems, '\n') or nil
end

function M.analyze(parse, opts, cb)
  opts = opts or {}
  local granularity = opts.granularity or 'normal'
  assert(M.granularities[granularity], 'unknown granularity: ' .. granularity)
  local max_chars = opts.max_chars or 400000
  local attempt = 0

  local function run(feedback)
    attempt = attempt + 1
    local prompt = build_prompt(parse, granularity, feedback)
    if #prompt > max_chars then
      return cb(nil, ('diff too large for one analysis: %d chars (limit %d)'):format(#prompt, max_chars))
    end
    local cmd = { 'claude', '-p', '--output-format', 'json', '--json-schema', SCHEMA }
    if opts.model then vim.list_extend(cmd, { '--model', opts.model }) end
    vim.system(cmd, { text = true, stdin = prompt, cwd = parse.root, timeout = opts.timeout or 300000 }, function(res)
      vim.schedule(function()
        if res.code ~= 0 then
          local err = vim.trim((res.stderr ~= '' and res.stderr or res.stdout) or '')
          return cb(nil, 'claude failed: ' .. err)
        end
        local ok, outer = pcall(vim.json.decode, res.stdout)
        if not ok then
          return cb(nil, 'unparseable claude output: ' .. res.stdout:sub(1, 200))
        end
        local payload = outer.structured_output
        if (payload == nil or payload == vim.NIL) and type(outer.result) == 'string' then
          local ok2, dec = pcall(vim.json.decode, outer.result)
          payload = ok2 and dec or nil
        end
        if type(payload) ~= 'table' or type(payload.groups) ~= 'table' then
          return cb(nil, 'no structured groups in claude output')
        end
        local problems = validate(parse, payload.groups)
        if problems and attempt == 1 then
          vim.notify('regroup: grouping invalid, retrying once...', vim.log.levels.WARN)
          return run('Your previous grouping was invalid:\n' .. problems .. '\nProduce a corrected, complete grouping.')
        end
        if problems then
          return cb(nil, 'invalid grouping after retry:\n' .. problems)
        end
        cb(payload.groups)
      end)
    end)
  end

  run(nil)
end

return M
