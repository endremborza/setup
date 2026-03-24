# Code Style Philosophy
- Performance is a high priority, but maintainability is a close second
- Minimal comments - code should be self-documenting
- Avoid dependencies unless super necessary or very mature and reliable or performance critical ones
  - definitely avoid building a large complex dependency tree
- DRY - no duplication
- Elegant, maintainable code over clever tricks
- Prefer composition and small, focused functions

# Language Standards
## Python
- Type hints required, pyright works on my nvim setup
- Tools: ruff does my formatting on my nvim, uv manages environments in .venv
  - never use pip, always use uv, for scripts /mnt/data/pytools is a globally used environment that can be used
- Prefer dataclasses for structured data
- Prefer functional design with minimal mutations for data heavy workloads


## Svelte
- Always typescript
- Component composition over prop drilling  
- Extract complex logic to utils
- Keep components small
- No business logic inside markup

## Rust
- Take a moment for performance concerns, always
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

## Latex
- use tectonic to render
- never copy tables, figures or data directly into the main, narrative .tex file, always generate them programmatically from the raw source 
  

# Workflow
- Run tests after changes
- I will do the committing myself

# Planning Flow
- write out plans to md files relevant in the repository
- when part of a plan is completed, completely remove it from the planning .md, you can add it to a different file if that is necessary, but we follow changes through git, not having crossed out todo points in a md

# Performance Mindset
- Consider algorithmic complexity.
- Mention time/space complexity when non-trivial.
- Avoid unnecessary allocations.
- Prefer data-oriented design where appropriate.

# Response Expectations
- Be concise.
- Do not include tutorial-style commentary.
- If something is ambiguous, ask one precise clarifying question.

# Decision Heuristics
- Prefer simpler architecture over micro-optimizations unless performance is proven to be critical.
- Optimize only after identifying a bottleneck.
- Avoid premature abstraction.
- If performance and readability conflict, prefer readability unless this is hot-path code.
- If introducing a dependency, explain why it is superior to a small custom implementation.

# Error Handling
- Fail loudly and early in internal tools.
- Avoid defensive over-engineering.
- Use clear error types instead of strings.
- Avoid unnecessary error abstraction layers.

# Testing
- Write minimal but meaningful tests.
- Test behavior, not implementation details.
- Avoid redundant tests.
- Prefer simple unit tests over heavy integration scaffolding unless instructed.
