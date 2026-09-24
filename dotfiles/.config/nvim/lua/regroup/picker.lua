local M = {}

-- Selection, multi-selection, in-place refresh and i+n binding for a telescope picker.
-- `make_finder` rebuilds the finder for refresh(); pass nil when the picker never refreshes.
function M.tools(prompt_bufnr, map, make_finder)
  local action_state = require('telescope.actions.state')
  local actions = require('telescope.actions')
  local tools = {}

  -- this picker's own selection: telescope's global selected entry outlives a closed picker
  function tools.selected()
    local p = action_state.get_current_picker(prompt_bufnr)
    local entry = p and p:get_selection()
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

  function tools.close()
    actions.close(prompt_bufnr)
  end

  -- keeps the cursor row across the finder swap
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

-- A list picker over `results()` (called again on refresh; `empty` is notified instead of
-- opening on nothing); `entry(v)` gives {display, ordinal}, `preview(v)` the preview lines
-- shown with filetype `preview_ft`. Each key is {lhs, desc, fn, close=?, picked=?, any=?}:
-- fn(v, tools) gets the selected value (skipped when nothing is selected), the picked
-- list with `picked`, or nothing with `any`; `close` closes the picker first.
function M.open(opts)
  local first = opts.results()
  if #first == 0 and opts.empty then return vim.notify(opts.empty, vim.log.levels.INFO) end
  local pickers = require('telescope.pickers')
  local finders = require('telescope.finders')
  local conf = require('telescope.config').values
  local previewers = require('telescope.previewers')

  local function make_finder(results)
    return finders.new_table {
      results = results,
      entry_maker = function(v)
        local e = opts.entry(v)
        e.value = v
        return e
      end,
    }
  end

  pickers.new({}, {
    prompt_title = opts.title,
    default_selection_index = opts.default_index,
    finder = make_finder(first),
    sorter = conf.generic_sorter({}),
    previewer = opts.preview and previewers.new_buffer_previewer {
      title = opts.preview_title,
      define_preview = function(self, entry)
        vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, opts.preview(entry.value))
        if opts.preview_ft then vim.bo[self.state.bufnr].filetype = opts.preview_ft end
      end,
    } or nil,
    attach_mappings = function(prompt_bufnr, map)
      local t = M.tools(prompt_bufnr, map, function() return make_finder(opts.results()) end)
      for _, k in ipairs(opts.keys) do
        t.bind(k[1], k[2], function()
          local v
          if k.picked then
            v = t.picked()
            if #v == 0 then return end
          elseif not k.any then
            v = t.selected()
            if v == nil then return end
          end
          if k.close then t.close() end
          k[3](v, t)
        end)
      end
      return true
    end,
  }):find()
end

return M
