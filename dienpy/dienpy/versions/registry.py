from dataclasses import dataclass
from typing import Callable

import setup.steps.base  # noqa: F401 — populates REGISTRY
import setup.steps.desktop  # noqa: F401
import setup.steps.dev  # noqa: F401
import setup.steps.workstation  # noqa: F401
from setup.runner import REGISTRY, Step
from setup.util import extended_env, run_cmd


@dataclass
class ToolEntry:
    level: int
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
    step_map: dict[str, Step] = {s.name: s for s in REGISTRY}
    result: dict[str, ToolEntry] = {}
    for name in _TRACKED:
        if name not in step_map:
            continue
        s = step_map[name]
        entry = ToolEntry(level=s.level, check=s.check, install_fn=s.fn)
        if name == "rust":
            entry.upgrade_fn = _rustup_update
        result[name] = entry
    result["bun"] = ToolEntry(
        level=1,
        check="bun --version",
        install_fn=_bun_install,
        upgrade_fn=_bun_upgrade,
    )
    return result


TOOLS: dict[str, ToolEntry] = _build()
