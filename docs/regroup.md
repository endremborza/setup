# Regroup — AI change-group review

Regroup turns the uncommitted diff into semantic **change groups** — future commits with titles and messages — and lets you review, stage, and commit them group by group.

Two components, one interface: the engine (**`dienpy hunks`**, Python) analyzes the diff and owns the cache at `.git/regroup-cache.json`; the UI (**`:Regroup`**, nvim `dotfiles/.config/nvim/lua/regroup/`) reads that cache and acts on the worktree. nvim never invokes the engine — picking an uncached config yanks the `dienpy hunks run` command instead of running it — and writes back only group marks and manual hunk moves.

**The model never writes a diff.** It only references hunks by content-addressed ID; diff parsing, patch reconstruction, and application are local and deterministic. A corrupt patch is impossible; a bad grouping is just a bad grouping.

## Hunks and IDs

A hunk is the unit of change, parsed locally from `git diff HEAD` (untracked files are diffed against `/dev/null`; new/deleted/renamed/binary files are one whole-file hunk). Its ID is `sha256(path + "\x1f" + body)[:12]`, with a `~n` suffix for duplicates in parse order.

IDs must match byte-for-byte between `dienpy/dienpy/hunks/_hunks.py` and nvim's `regroup/diff.lua` — pinned by `dienpy/tests/test_hunks_parity.py`; change both together. A mismatch fails safe: the nvim side reads the cache as fully stale.

Content addressing makes staleness a pure function of (repo, cache): drift detection is a set comparison, no daemon or state anywhere.

## Anchors, rebind, sync

Editing a hunk mid-review mints a new ID. Each cache entry therefore stores the HEAD-side range (`@@ -start,count`; count 0 means the path is the anchor) of every live hunk next to the `head` sha; `dienpy hunks sync` matches live hunks against those anchors and carries edited hunks back into their groups without a model call (`dienpy/dienpy/hunks/_rebind.py`). nvim calls `sync` whenever the live and grouped ID sets disagree, so an edit is not a re-analysis. A rebind that could land in more than one group is flagged `ambiguous` rather than guessed.

## The cache

`.git/regroup-cache.json` (schema v3, owner `dienpy/dienpy/hunks/_cache.py`): `analyses` keyed by `granularity|model|context`, each entry holding `ids` (the hunks its groups cover), `groups` (`[{title, message, hunks, mixed?, ambiguous?}]`), `anchors` + `head` (the rebind side), `config` and `time`; plus `last`, the most recently used config. Every hunks command prunes entries that no longer describe any part of the current diff.

## Config dimensions

Analyses are keyed by three dimensions, given as bare tokens in any order (missing ones fall back to the last run, then defaults):

- **granularity** — `loose` (broad themes) | `normal` (atomic commits) | `granular` (smallest self-consistent units)
- **model** — an AI profile name (below); the builtin profiles `haiku|sonnet|opus|fable` map to the claude CLI, and an unknown token passes through as a bare claude model id. The nvim picker lists `dienpy ai profiles` (override with `setup { models = {...} }`)
- **context** — `bare` (hunks only) | `agents` (AGENTS.md in the prompt) | `explore` (agent may also read repo files — needs a backend with tool access)

## AI backends

Model access goes through `dienpy.ai` ([dienpy/AGENTS.md](../dienpy/AGENTS.md#the-ai-package)): the model dimension names a profile from `~/.config/dienpy/ai.toml`, and the engine declares what it needs — schema output, plus repo tools for `explore` — so a profile that cannot serve the need is refused before anything is spent or written.

Grouping via a local or SSH-tunneled OpenAI-compatible server is one profile away:

```toml
[profile.tunnel]
kind = "openai"
url = "http://localhost:8081/v1/chat/completions"
```

```
dienpy hunks run tunnel bare
```

The `cli` profiles run `claude -p --json-schema` on **login auth**: the subprocess drops `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` so the claude command uses its own claude.ai credentials; `--auth env` keeps them.

## Commands

```
dienpy hunks run [dims] [--path P] [--staged] [--force|--full] [--auth login|env]
dienpy hunks list        cached runs + coverage against the current diff
dienpy hunks drift       kept/rebound/gone/new (exit 1 = drifted, 2 = no run)
dienpy hunks sync        rebind edited hunks into their groups, no model call
dienpy hunks improve     rewrite a past commit's message
dienpy hunks history     describe commits: hashes, or --since 7D / 50h
```

`run` is incremental: when a cached entry covers at least half of the current hunks, only the new hunks are sent along with the existing group titles and placed via `extends`; `--force`/`--full` or low coverage re-runs fully. A grouping that drops or duplicates a hunk id is rejected locally and retried once with the violation report; still-invalid output is a hard error.

`--path <dir|file>` scopes a run to one subtree: only those hunks reach the model, groups covering the rest of the diff survive untouched, and the entry records the partial coverage, so the remaining hunks land incrementally on the next unscoped run.

`--staged` analyzes the index instead of the worktree and prints groups with full messages without touching the cache — the "message for what I'm about to commit" path; at `loose` granularity that is a single suggested commit message.

`improve` and `history` are the post-commit half of the same pipeline: same repo context and style anchor (recent commit subjects) as the grouping prompts, same backend layer (`--profile`, `--effort`; `--max-diff-chars` truncates per-commit diffs for small models). `history` prints; `--out FILE` appends there.

## nvim UI

`<leader>gg` opens the three-dimension config menu, `:Regroup` the group picker; `]g`/`[g` navigate hunks within the current group; stage/unstage/revert/commit act per group or hunk; `<C-o>` moves a hunk to another group; burying a group stashes it (`regroup:`-tagged, `:RegroupGraveyard` restores). Cheatsheet: `:h regroup` (`dotfiles/.config/nvim/doc/regroup.txt`).

## Integrations

`cril housekeeping --hunks` shells out to `dienpy hunks run --path` to pre-group one subtree's notes inside a larger diff.
