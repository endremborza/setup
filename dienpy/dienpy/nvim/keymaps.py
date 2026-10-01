"""Dump the live keymaps: config loaded, a buffer with its LSP and gitsigns attached."""

import json as jsonlib
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from ._shared import ARGS_ENV, run_headless

# Lua-defined maps record their script only when nvim starts verbose; without it
# every one reports the anonymous Lua sid and config, plugin and default look alike.
_FLAGS = ("-V1", "-n")

_LUA = rf"""
local args = vim.json.decode(vim.env.{ARGS_ENV})
local MODES = {{ 'n', 'x', 'o', 'i' }}
local config_dir = vim.fn.stdpath('config')

local function origin(sid)
  local info = sid and sid > 0 and vim.fn.getscriptinfo({{ sid = sid }})[1]
  local name = info and info.name or ''
  if name:find('vim/_core/', 1, true) or vim.startswith(name, vim.env.VIMRUNTIME) then
    return 'default'
  end
  -- lazy.nvim installs the `keys` of the config's plugin specs from its handler
  if vim.startswith(name, config_dir) or name:find('lazy/core/handler/keys.lua', 1, true) then
    return 'config'
  end
  return 'plugin'
end

local function key(lhs)
  return vim.fn.keytrans(vim.keycode(lhs))
end

local function buf_map_count()
  local n = 0
  for _, mode in ipairs(MODES) do n = n + #vim.api.nvim_buf_get_keymap(0, mode) end
  return n
end

-- which-key names its groups only after its own deferred setup has run
local function groups()
  if not package.loaded['which-key'] then return {{}} end
  local cfg = require('which-key.config')
  vim.wait(3000, function() return cfg.loaded end, 50)
  local out = {{}}
  for _, m in ipairs(cfg.mappings) do
    if m.group and m.desc and m.mode == 'n' then out[key(m.lhs)] = m.desc end
  end
  return out
end

local function dump()
  local maps = {{}}
  for _, mode in ipairs(MODES) do
    -- buffer-local maps shadow global ones on the same lhs
    for _, src in ipairs({{ vim.api.nvim_get_keymap(mode), vim.api.nvim_buf_get_keymap(0, mode) }}) do
      for _, m in ipairs(src) do
        -- which-key's own prefix triggers are plumbing, not bindings
        if m.desc and m.desc ~= '' and not vim.startswith(m.desc, 'which-key-trigger') then
          maps[mode .. '\0' .. m.lhs] = {{ mode = mode, lhs = key(m.lhs), desc = m.desc, origin = origin(m.sid) }}
        end
      end
    end
  end
  return vim.tbl_values(maps)
end

vim.api.nvim_create_autocmd('VimEnter', {{ once = true, callback = vim.schedule_wrap(function()
  -- headless nvim has no UIEnter, so lazy.nvim never fires VeryLazy on its own
  vim.api.nvim_exec_autocmds('User', {{ pattern = 'VeryLazy' }})
  vim.cmd.edit(vim.fn.fnameescape(args.file))
  vim.wait(10000, function() return #vim.lsp.get_clients({{ bufnr = 0 }}) > 0 end, 50)
  -- attaches finish asynchronously; done once the buffer's maps stop changing
  local last, since = -1, vim.uv.now()
  vim.wait(5000, function()
    local n = buf_map_count()
    if n ~= last then last, since = n, vim.uv.now() end
    return vim.uv.now() - since >= 800
  end, 100)
  local result = {{
    version = string.format('%d.%d.%d', vim.version().major, vim.version().minor, vim.version().patch),
    leader = key(vim.g.mapleader or '\\'),
    groups = groups(),
    maps = dump(),
  }}
  io.write('\nKEYMAPS:' .. vim.json.encode(result) .. '\n')
  vim.cmd('qa!')
end) }})
"""


@dataclass(frozen=True)
class Keymap:
    mode: str
    lhs: str
    desc: str
    origin: str  # config | plugin | default


@dataclass(frozen=True)
class Keymaps:
    version: str
    leader: str
    groups: dict[str, str]  # which-key group prefix -> name
    maps: list[Keymap]


def dump(file: Path | None = None) -> Keymaps:
    """Keymaps with a description, as nvim holds them in a buffer of `file` (default: $MYVIMRC)."""
    target = file or Path(
        os.environ.get("MYVIMRC", Path.home() / ".config/nvim/init.lua")
    )
    h = run_headless(_LUA, {"file": str(target)}, "KEYMAPS:", 40, flags=_FLAGS)
    if h.data is None:
        raise SystemExit(
            "keymap dump: " + ("timed out" if h.timed_out else h.output[-500:])
        )
    maps = sorted((Keymap(**m) for m in h.data["maps"]), key=lambda m: (m.lhs, m.mode))
    return Keymaps(h.data["version"], h.data["leader"], h.data["groups"] or {}, maps)


def main(file: str = "", *, json: bool = False) -> None:
    """Print the live keymaps that carry a description (origin, mode, lhs, desc)."""
    km = dump(Path(file) if file else None)
    if json:
        print(jsonlib.dumps(asdict(km), indent=1))
        return
    for m in km.maps:
        print(f"{m.origin:8} {m.mode}  {m.lhs:16} {m.desc}")
