"""List AI profiles: backend kind, config, default marker and tool bindings."""

from .._out import table
from . import _profiles


def main() -> None:
    default = _profiles.default_name()
    bound: dict[str, list[str]] = {}
    for tool, prof in sorted(_profiles.bindings().items()):
        bound.setdefault(prof, []).append(tool)
    rows = []
    for name in _profiles.names():
        spec = _profiles.get(name)
        detail = " ".join(f"{k}={v}" for k, v in spec.items() if k != "kind")
        marks = (["default"] if name == default else []) + bound.get(name, [])
        suffix = f"  ({', '.join(marks)})" if marks else ""
        rows.append((name, spec.get("kind", "?"), detail + suffix))
    print(table(rows))
