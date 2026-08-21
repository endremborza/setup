"""Group-list helpers shared by the hunks commands."""


def sanitize(groups: list[dict], live: set[str]) -> list[dict]:
    """Drop hunk ids gone from the diff, drop emptied groups, merge same-titled groups."""
    out: list[dict] = []
    by_title: dict[str, dict] = {}
    for g in groups:
        hunks = [i for i in g["hunks"] if i in live]
        if not hunks:
            continue
        mixed = [m for m in g.get("mixed") or [] if m["hunk"] in live]
        flagged = [i for i in g.get("ambiguous") or [] if i in live]
        tgt = by_title.get(g["title"])
        if tgt is None:
            tgt = {k: v for k, v in g.items() if k not in ("mixed", "ambiguous")}
            tgt["hunks"] = hunks
            by_title[g["title"]] = tgt
            out.append(tgt)
        else:
            tgt["hunks"] = tgt["hunks"] + hunks
        if mixed:
            tgt["mixed"] = (tgt.get("mixed") or []) + mixed
        if flagged:
            tgt["ambiguous"] = (tgt.get("ambiguous") or []) + flagged
    return out


def print_groups(groups: list[dict], live: set[str]) -> None:
    for g in groups:
        n = sum(1 for i in g["hunks"] if i in live)
        print(f"{n:2d} hunks  {g['title']}")
        for m in g.get("mixed") or []:
            print(f"          mixed {m['hunk']}: {m['note']}")
        for i in g.get("ambiguous") or []:
            print(f"          ambiguous {i}: rebound across group boundaries")
