from dataclasses import dataclass
from typing import Callable

import setup.bricks.base  # noqa: F401 — populates REGISTRY
import setup.bricks.desktop  # noqa: F401
import setup.bricks.dev  # noqa: F401
import setup.bricks.workstation  # noqa: F401
from setup.runner import REGISTRY, Brick
from setup.util import extended_env, run_cmd


@dataclass
class ToolEntry:
    check: str | None
    install_fn: Callable[[], None]
    upgrade_fn: Callable[[], None] | None = None


def _rustup_update() -> None:
    run_cmd("rustup update stable", env=extended_env())


def _bun_install() -> None:
    run_cmd("sh -c 'curl -fsSL https://bun.sh/install | bash'")


def _bun_upgrade() -> None:
    run_cmd("bun upgrade", env=extended_env())


_TRACKED = {
    "rust",
    "lua",
    "luarocks",
    "jq",
    "neovim",
    "fzf",
    "tmux",
    "alacritty",
    "nerd-fonts",
    "logseq",
}


def _build() -> dict[str, ToolEntry]:
    brick_map: dict[str, Brick] = {b.name: b for b in REGISTRY}
    result: dict[str, ToolEntry] = {}
    for name in _TRACKED:
        if name not in brick_map:
            continue
        b = brick_map[name]
        entry = ToolEntry(check=b.check, install_fn=b.fn)
        if name == "rust":
            entry.upgrade_fn = _rustup_update
        result[name] = entry
    result["bun"] = ToolEntry(
        check="bun --version",
        install_fn=_bun_install,
        upgrade_fn=_bun_upgrade,
    )
    return result


TOOLS: dict[str, ToolEntry] = _build()
