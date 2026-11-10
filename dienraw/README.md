# dienraw

The bottom of the tree: helpers that `moac`, `dienpy`, `hyppy`, `cril` and `fleet` all import, so each exists once. It imports none of them.

- `dienraw.out`: tables, section headers, the y/N prompt, compact markdown tables.
- `dienraw.toml`: TOML values out, TOML in with a loud error, atomic writes.

No personal paths or machine-specific config. The one dependency is `rich`, for terminal tables.
