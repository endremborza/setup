# Regroup — patches, patch branches, landings

Regroup partitions the uncommitted diff into **patches** — sets of hunks that apply and commit as a unit, each with a commit title and message — and lands them: committed straight onto the default branch, or committed onto a **patch branch** whose history is squashed into one **landing** commit when the work is done. The engine is `dienpy hunks` (Python); nvim's `:Regroup` is a viewer over it that runs the odd plain git command itself.

Every git write goes through the engine, and **the model never writes a diff**: it only references hunks by content-addressed id, while patch reconstruction and application are local and deterministic. A corrupt patch is impossible; a bad partition is just a bad partition.

## Hunks and ids

A hunk is the unit of change, parsed from `git diff HEAD` (untracked files are diffed against `/dev/null`; a binary, empty or purely renamed file is one whole-file entry). Its id is `sha256(path + "\x1f" + body)[:12]`, with a `~n` suffix for duplicates in parse order. The `@@` header is not hashed, so a hunk keeps its id while edits elsewhere shift its line numbers, and the same content in the index and in the worktree diff yields the same id — "is this hunk staged" is a set membership test, and no state records it (`dienpy/dienpy/hunks/_hunks.py`).

An edit inside a hunk mints a new id: the hunk leaves its patch and shows up as unassigned, to be placed by the model (`run --extend`) or by hand (`patch move`). Nothing rebinds — a patch is meant to be committed minutes after it is computed, and from then on git owns its identity.

## Patches and the cache

`.git/regroup-cache.json` (schema v4, owner `_cache.py`): `analyses` keyed by `granularity|model|context`, each entry holding `patches` (`[{id, title, message, hunks, mixed?}]`), the hunk `ids` they cover, `config` and `time`; plus `last`, the run the shell and nvim act on (`hunks use` changes it). A patch id is minted once, when the model's output is accepted, and is what every command addresses it by; positions work too. Every hunks command prunes entries that no longer describe any live hunk.

Config dimensions, given as bare tokens in any order (missing ones fall back to the last run, then defaults): **granularity** `loose|normal|granular`, **model** (an AI profile name; unknown tokens pass through as bare claude model ids), **context** `bare|agents|explore` (`explore` lets the model read repo files before partitioning).

## Commands

```
dienpy hunks run [dims] [--path P] [--staged] [--force|--full|--extend] [--auth login|env]
dienpy hunks list [--json]                 cached runs + coverage; --json is what nvim reads
dienpy hunks use [dims]                    make a cached run the current one
dienpy hunks patch stage|unstage|discard <patch|hunk-id …>
dienpy hunks patch bury <patch>            stash under the graveyard prefix `regroup: <title>`
dienpy hunks patch commit <patch …> [--message M]
dienpy hunks patch move <hunk-id …> <patch>
dienpy hunks branch new <name> [patch …] [--worktree]
dienpy hunks branch land [name] [--onto B] [--split [granularity]] [--message M]
dienpy hunks branch show [name] [--archived] [--json]
dienpy hunks branch drop <name>
dienpy hunks improve <hash>                rewrite a past commit's message
dienpy hunks history <hashes> | --since 7D
```

`run` is incremental: when a cached entry covers at least half of the current hunks, only the new ones are sent along with the existing titles and placed via `extends`, and the patches that grew are re-described in the same run. `--extend` pins that path — it requires a cached run and refuses rather than re-partitioning, which is why it is the one analysis nvim binds to a key. `--path` scopes a run to one subtree, leaving patches over the rest of the diff untouched. `--staged` partitions the index and prints messages without touching the cache. A partition that drops or duplicates a hunk id is rejected locally and retried once with the violation report.

`patch commit` commits on whatever branch is checked out: on the default branch that is the direct landing of a patch; on a patch branch it is how the branch gets built. The index may hold nothing beyond the patch (a staged rename is the one exception — index-side noise the worktree diff folds into content hunks, whose patch headers are rebased onto the new path before `git apply`).

## The patch-branch protocol

Triage empties the worktree: every patch ends committed on the default branch, committed on a patch branch, buried, or discarded. Leftovers are allowed, but a leftover is what makes a branch switch need a stash, so `branch new` carries them along and `branch land` stashes and pops them.

- `branch new <name> <patches>` switches in place to a new branch at HEAD (dirty files carried) and commits the picked patches on it in order. `--worktree` builds the branch in `../<repo>-<name>` instead, moving the picked patches over as a stash, so the current checkout stays on its branch — the shape an agent or a parallel branch needs.
- Commits on the branch are free-form; `git commit --fixup` for an edit spotted mid-review is fine, the landing erases it.
- `branch land` writes the message first (`--message`; a single commit's message as is; otherwise the model rewrites the branch log into one), stashes leftovers, switches to the default branch, `git merge --squash`, commits once, verifies the landing tree equals the branch tip when the base did not move, archives the tip under `refs/landed/<name>` with a note on the landing (`git notes --ref=landed`), deletes the branch and its worktree, pops the leftovers. A squash that conflicts is undone and reported: merge the default branch into the patch branch and land again. `--split` partitions the squashed diff and commits patch by patch instead, so a messy branch lands as a few clean commits — one landing is the `loose` case of the same engine.
- Landing closes the branch; continuing means a new patch branch from the default branch.
- `branch drop` archives under `refs/dropped/<name>`. Both namespaces sit outside `refs/heads`: `git branch` does not list them, `git push` never sends them, `git log --all` and `git log refs/landed/<name>` still reach them.

## AI backends

Model access goes through `dienpy.ai` ([dienpy/AGENTS.md](../dienpy/AGENTS.md#the-ai-package)): the model dimension names a profile from `~/.config/dienpy/ai.toml`, and the engine declares what it needs (schema output, repo tools for `explore`), so a profile that cannot serve the need is refused before anything is spent or written. The `cli` profiles run `claude -p --json-schema` on login auth: the subprocess drops `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`; `--auth env` keeps them. `branch land` uses the `commit` tool profile for its message.

## nvim

`dotfiles/.config/nvim/lua/regroup/` parses no diff and writes no git state: `state.lua` reads `hunks list --json`, `ui.lua` calls `hunks patch …`, `hunks branch …`, `hunks use` and `hunks run --extend`, forwarding a config it read from the listing, and reloads after each. `review.lua` (diff windows) and `commit.lua` (commit buffer) are plain-git views shared with the `<leader>gf/gr/gb` pickers in `init.lua`; `graveyard.lua` is `git stash list` filtered on the prefix.

The seam has two rules the engine and the plugin both keep: a `--json` payload owns stdout alone, every diagnostic (prune included) goes to stderr; and a command's exit status is the write's alone — a reload that fails after a successful write is reported on its own, since retrying would apply the same patch twice.

`<leader>gg` opens the patch picker on the current run, `<leader>gG` the run picker; `:Regroup <tokens>` narrows to one cached run; `:RegroupBranches` lists patch branches (switch, land, drop); `:RegroupGraveyard` restores buried patches. Hunks no patch covers collect in a synthetic "(unassigned new changes)" patch. Cheatsheet: `:h regroup`.

## Integrations

`cril housekeeping --hunks` shells out to `dienpy hunks run --path` to pre-partition one subtree inside a larger diff. `dienpy feed run` closes every unattended session with `run --extend` on the dims it was given (a full run when nothing is cached).
