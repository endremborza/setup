"""List AI profiles: backend kind, config, default marker and tool bindings, what serves each
and whether it is up; where the config and the ledger of past calls are."""

from dienraw.out import table

from . import _ledger, _profiles, _serve


def _served(name: str, spec: dict) -> str:
    """Up or down for a profile with a `serve` unit, with what the endpoint reports when up."""
    served = str(spec.get(_serve.FIELD, ""))
    if not served:
        return ""
    if not _serve.active(served):
        return f"down (moac up {name})"
    found = _serve.reports(spec)
    return " ".join(["up", *(f"{k}={v}" for k, v in found.items())])


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
        rows.append((name, spec.get("kind", "?"), detail + suffix, _served(name, spec)))
    print(table(rows))
    path = _profiles.PATH
    target = f" -> {path.resolve()}" if path.is_symlink() else ""
    print(f"config {path}{target}" if path.exists() else f"config {path} (none)")
    print(f"ledger {_ledger.PATH} (moac ledger)")
