"""Patch assembly from hunk ids, and the git calls that stage, unstage, discard, bury and commit them.

The index and the worktree diff are two views of one change, and hunk ids agree only
where the views agree. A staged `git mv` is a whole-file entry in the index while the
worktree diff folds the move into the renamed file's content hunks under the new path:
patches for such a file are rebased onto the new path, the only one the index still
has, and the commit guard skips the move itself. An unstaged edit within a staged
hunk's context merges both into one worktree hunk the index does not hold; the index
hunks clashing with it (same path, overlapping HEAD lines) are what staging or
unstaging that merged hunk clears first. Every entry point takes both views parsed,
so a command parses each once.
"""

from ._hunks import Hunk, raw, repo, unquote

GRAVEYARD = "regroup: "


def by_id(hunks: list[Hunk]) -> dict[str, Hunk]:
    return {h.id: h for h in hunks}


def rename_source(h: Hunk) -> str | None:
    for line in h.header.split("\n"):
        if line.startswith("rename from "):
            return unquote(line[len("rename from ") :])
    return None


def staged_renames(index: list[Hunk]) -> set[str]:
    return {h.path for h in index if rename_source(h)}


def _rebase_header(header: str) -> str:
    """The header of a renamed file, addressed by its new path on both sides — git's own
    spelling of that path (quoting, trailing tab) comes from the `+++` line."""
    lines = header.split("\n")
    new = next(ln[4:] for ln in lines if ln.startswith("+++ "))
    b = new.rstrip("\t")
    out = []
    for line in lines:
        if line.startswith("diff --git "):
            out.append(f"diff --git {b.replace('b/', 'a/', 1)} {b}")
        elif line.startswith("--- "):
            out.append("--- " + new.replace("b/", "a/", 1))
        elif not line.startswith(("similarity index ", "rename from ", "rename to ")):
            out.append(line)
    return "\n".join(out)


def _whole_families(hunks: list[Hunk], sel: set[str]) -> None:
    """Identical hunks differ only by parse order, which the index and worktree views do
    not share, and git apply lands a lone one on whichever twin's context comes first."""
    families: dict[str, list[str]] = {}
    for h in hunks:
        families.setdefault(h.id.split("~")[0], []).append(h.id)
    for members in families.values():
        if len(members) > 1 and not sel.isdisjoint(members) and not sel >= set(members):
            raise SystemExit(
                f"hunks {', '.join(members)} are identical — act on all of them at once "
                "(`patch move` them into one patch)"
            )


def _split(
    hunks: list[Hunk], ids: list[str], renamed: set[str]
) -> tuple[str | None, list[str]]:
    """Patch text for the content hunks among `ids` (file header once per file), and the
    paths of the whole-file entries, which git handles by path."""
    sel = set(ids)
    unknown = sel - {h.id for h in hunks}
    if unknown:
        raise SystemExit(f"unknown hunk id(s): {', '.join(sorted(unknown))}")
    _whole_families(hunks, sel)
    patch: list[str] = []
    paths: list[str] = []
    seen_header: set[str] = set()

    def add_path(p: str | None) -> None:
        if p and p not in paths:
            paths.append(p)

    for h in hunks:
        if h.id not in sel:
            continue
        if h.kind == "hunk":
            if h.header not in seen_header:
                seen_header.add(h.header)
                patch.append(
                    _rebase_header(h.header) if h.path in renamed else h.header
                )
            patch.append(h.text)
        else:
            add_path(h.path)
            add_path(rename_source(h))
    return ("\n".join(patch) + "\n") if patch else None, paths


def _apply(root: str, patch: str, *flags: str) -> None:
    raw(repo(root), "apply", *flags, "--whitespace=nowarn", "-", stdin=patch)


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    (s1, n1), (s2, n2) = a, b
    return s1 < s2 + max(n2, 1) and s2 < s1 + max(n1, 1)


def clashes(index: list[Hunk], live: list[Hunk], targets: list[Hunk]) -> list[str]:
    """Index hunks the worktree view no longer has, where `targets` change the same file."""
    live_ids = {h.id for h in live}
    out: list[str] = []
    for s in index:
        if s.id in live_ids or rename_source(s):
            continue
        for t in targets:
            if s.path == t.path and (
                s.kind != "hunk" or t.kind != "hunk" or _overlap(s.old_span, t.old_span)
            ):
                out.append(s.id)
                break
    return out


def stage(root: str, ids: list[str], live: list[Hunk], index: list[Hunk]) -> int:
    """Stage the live hunks among `ids` that the index does not hold yet."""
    held = by_id(index)
    recs = by_id(live)
    todo = [i for i in ids if i not in held]
    clash = clashes(index, live, [recs[i] for i in todo if i in recs])
    if clash:
        unstage(root, clash, live, index)
    patch, paths = _split(live, todo, staged_renames(index))
    if patch:
        _apply(root, patch, "--cached")
    if paths:
        raw(repo(root), "add", "--", *paths)
    return len(todo)


def unstage(root: str, ids: list[str], live: list[Hunk], index: list[Hunk]) -> int:
    held = by_id(index)
    recs = by_id(live)
    todo = [i for i in ids if i in held]
    todo += clashes(index, live, [recs[i] for i in ids if i in recs and i not in held])
    patch, paths = _split(index, todo, staged_renames(index))
    if patch:
        _apply(root, patch, "--cached", "--reverse")
    if paths:
        raw(repo(root), "restore", "--staged", "--", *paths)
    return len(todo)


def _worktree_paths(h: Hunk) -> list[tuple[str, bool]]:
    """A whole-file entry's paths, each with whether HEAD has it."""
    if h.kind == "untracked" or "\nnew file mode " in h.header:
        return [(h.path, False)]
    if "\ndeleted file mode " in h.header:
        return [(h.path, True)]
    src = rename_source(h)
    return [(h.path, False), (src, True)] if src else [(h.path, True)]


def discard(root: str, ids: list[str], live: list[Hunk], index: list[Hunk]) -> int:
    """Return the hunks to their HEAD state in both the index and the worktree; an id
    only the index holds is unstaged, the worktree keeps what the merged hunk has."""
    unstage(root, ids, live, index)
    recs = by_id(live)
    content = [i for i in ids if i in recs and recs[i].kind == "hunk"]
    patch, _ = _split(live, content, staged_renames(index))
    if patch:
        _apply(root, patch, "--reverse")
    restore: list[str] = []
    clean: list[str] = []
    for i in ids:
        h = recs.get(i)
        if h is None or h.kind == "hunk":
            continue
        for p, in_head in _worktree_paths(h):
            (restore if in_head else clean).append(p)
    r = repo(root)
    if restore:
        raw(r, "restore", "--source=HEAD", "--worktree", "--", *restore)
    if clean:
        raw(r, "clean", "-f", "--", *clean)
    return len(ids)


def guard_foreign(index: list[Hunk], ids: list[str]) -> None:
    """The index may hold nothing beyond `ids` except a staged rename, which is
    index-side noise the worktree diff folds into content hunks."""
    sel = set(ids)
    for h in index:
        if h.id not in sel and not (h.kind == "file" and rename_source(h)):
            raise SystemExit(
                f"index contains changes outside the patch ({h.id} {h.path}) — "
                "commit or unstage those first"
            )


def stage_alone(root: str, ids: list[str], live: list[Hunk], index: list[Hunk]) -> None:
    """Stage `ids` into an index that holds nothing else — the guard runs first, so a
    refusal changes nothing."""
    guard_foreign(index, ids)
    stage(root, ids, live, index)


def bury(
    root: str, ids: list[str], title: str, live: list[Hunk], index: list[Hunk]
) -> None:
    stage_alone(root, ids, live, index)
    raw(repo(root), "stash", "push", "--staged", "-q", "-m", GRAVEYARD + title)


def commit_staged(root: str, message: str) -> str:
    """Commit the index; returns the short hash."""
    r = repo(root)
    raw(r, "commit", "-q", "-F", "-", stdin=message)
    return r.out("rev-parse", "--short", "HEAD")


def commit(
    root: str, ids: list[str], message: str, live: list[Hunk], index: list[Hunk]
) -> str:
    stage_alone(root, ids, live, index)
    return commit_staged(root, message)
