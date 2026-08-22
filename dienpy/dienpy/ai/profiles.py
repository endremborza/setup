"""List AI profiles: backend kind, config, default marker and tool bindings."""

from . import _profiles


def main() -> None:
    default = _profiles.default_name()
    bound: dict[str, list[str]] = {}
    for tool, prof in sorted(_profiles.bindings().items()):
        bound.setdefault(prof, []).append(tool)
    for name in _profiles.names():
        spec = _profiles.get(name)
        detail = " ".join(f"{k}={v}" for k, v in spec.items() if k != "kind")
        marks = (["default"] if name == default else []) + bound.get(name, [])
        suffix = f"  ({', '.join(marks)})" if marks else ""
        print(f"{name:<12} {spec.get('kind', '?'):<7} {detail}{suffix}")
