# Workflow

## Version Control
- I will do the committing myself

## Commit Splitting -- dienpy hunks
- When discussing how to split/commit uncommitted changes, `dienpy hunks` is the shared vocabulary: reference its change groups by title instead of re-deriving a grouping.
- `dienpy hunks run [loose|normal|granular] [bare|agents|explore] [haiku|sonnet|opus|fable]` analyzes the repo's uncommitted diff into commit groups (cached, incremental); `dienpy hunks list` shows cached runs with coverage against the current diff; `dienpy hunks drift` reports kept/rebound/gone/new (exit 1 = drifted, 2 = no run); `dienpy hunks sync` rebinds hunks edited since the analysis back into their groups without calling a model.
- The cache is `.git/regroup-cache.json`: `analyses` keyed by `granularity|model|context`, each entry holding `ids` (hunk ids), `anchors`/`head` (HEAD-side ranges `sync` rebinds on) and `groups` (`[{title, message, hunks, ...}]`) -- readable directly when you need group contents.
- nvim's `:Regroup` picker reads the same cache, so a grouping agreed in conversation is what I see there; every hunks command auto-prunes cached runs that no longer cover any current hunk.

## Planning Flow
- write out plans to md files (see *Docs vs. .cril* for where each kind belongs)
- when part of a plan is completed, completely remove it from the planning .md, you can add it to a different file if that is necessary, but we follow changes through git, not having crossed out todo points in a md

## Docs vs. .cril

> a project might have a `.cril` directory, a symlink to a PKM system, if it is not present, disregard this part 

`.cril/` is the repo's slice of my cross-repo PKM (symlinked into each repo, gitignored, never committed). The split is by tense/audience:
- **`docs/` (committed)** = the project *as it is*, for anyone reading the code: architecture, data model, schemas, shipped-feature references, build/dev setup, benchmarks & results, anything cited externally (e.g. a paper).
- **`.cril/` (PKM, not committed)** = everything about *changing or running* the project, for me as its driver: todos/backlogs, plans & design explorations, ideas, engineering debt, launch/marketing copy, high-level progress notes, and reusable agent prompts/playbooks.

Invariants:
- `docs/` never links into `.cril/`; `.cril/` may link into the repo — the repo stays self-contained.
- When a `.cril/` plan ships, fold its *as-built* description into `docs/` and delete the plan (history lives in git, not stale checklists).
- An incident, a debugging session, a one-off request and whatever it taught go to `.cril/writeups/`, todos to `.cril/todo.md` — never into the code as comments (see *Comments*).

## Writing md
- One line per paragraph. Never hard-wrap prose at a column -- wrapping is the editor's job, and hard wraps make a one-word edit reflow the whole block in the diff.
- Same for list items and table rows: one line each, however long.
- Only real structure gets a linebreak: paragraph, list item, heading, code block.

## Response Expectations
- If something is ambiguous, or a plan is too complex with many possible paths, ask precise clarifying questions.
- Be concise.
- Do not include tutorial-style commentary.
- When a mistake is made, take note of it in a persistent way, to avoid making it again.

## Decision Heuristics
- Prefer simpler architecture over micro-optimizations unless performance is declared to be critical.
- Optimize only after identifying a bottleneck.
- Avoid premature abstraction, but do strive to find the ideal one. This is also an issue where clarifying questions are encouraged.
- If introducing a dependency, explain why it is superior to a small custom implementation.


# Coding

## Style Philosophy
- Performance is a high priority, but maintainability is a close second
- Minimal comments - code should be self-documenting
- Avoid dependencies unless super necessary or very mature and reliable or performance critical ones
  - definitely avoid building a large complex dependency tree
- DRY - no duplication
- Elegant, maintainable code over clever tricks
- Prefer composition and small, focused functions
- If a new feature supersedes or subsumes a previous one, the previous one should be replaced and deleted unless performance is harmed, but in all cases deletion should be brought up and considered

## Comments
- A comment describes a mechanism that is not evident from reading the code, or a constraint that still holds. Present tense, about the thing, not about the work that produced it.
- Never write the story: no incident, outage, debugging session, review remark, or request ("as requested", "you asked for", "after the report"), no dates, no commit/PR/issue references, no "changed from / used to / previously / for now / until we". Git holds the history and `.cril/` holds the writeups, todos and plans — code holds neither.
- Deciding what to keep: strip every reference to the episode and see what is left. Nothing left → delete the comment. A permanent constraint left → keep only that, as a fact ("the snap shim's epoch outranks any Mozilla version"), never as a war story ("unattended-upgrades swapped firefox on me").
- No TODO/FIXME/HACK markers in code — they belong in `.cril/todo.md`, where I actually look for them. No commented-out code, no "alternative kept for later", no one-off setup recipes for a machine or an account.
- Same rule for docstrings, config files, systemd units and scripts. The only exception is a file whose entire purpose is to be a note (`archive/`, scratch dirs).

## Performance Mindset
- Consider algorithmic complexity.
- Mention time/space complexity when non-trivial.
- Avoid unnecessary allocations.
- Prefer data-oriented design where appropriate.


## Language Standards
### Python
- In python, simplicity and maintainability are paramount
  - Unless specific performance requirements are noted
- Type hints required, pyright works on my nvim setup
- Tools: ruff does my formatting on my nvim, uv manages environments in .venv
  - never use pip, always use uv, for scripts try uv run by default (if .venv available, which will almost always be true in projects using python) us uv run for python scripts. otherwise /mnt/data/pytools is a globally used environment that can be used with some commonly used packages installed
- Prefer dataclasses for structured data
- Prefer functional design with minimal mutations for data heavy workloads

### Svelte
- Always typescript
- Component composition over prop drilling  
- Extract complex logic to utils
- Keep components small
- No business logic inside markup

### Rust
- Take a moment for performance concerns, always
  - in Rust, performance is always paramount
- Idiomatic patterns required
- Clear ownership semantics
- Avoid repetition and extra verbosity
- Benchmark before micro optimizing
- The rs file structure:
  - Always pubs first of a certain kind of declaration
  - The general order
        - imports
		- std, ext, crate
	- constants
	- types
	- macros
		- defs, calls
	- structs
	- enums
	- traits
	- impls
		- simple, trait
	- functions
	- modules
		- same structure within module


### Latex
- use tectonic to render
- never copy tables, figures or data directly into the main, narrative .tex file, always generate them programmatically from the raw source 

## Error Handling
- Fail loudly and early in internal tools.
- Avoid defensive over-engineering.
- Use clear error types instead of strings.
- Avoid unnecessary error abstraction layers.

## Testing
- Write minimal but meaningful tests.
- Test behavior, not implementation details.
- Avoid redundant tests.
- Prefer simple unit tests over heavy integration scaffolding unless instructed.
  
