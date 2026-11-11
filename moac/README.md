# moac

Models, options, accounts, capabilities: my opinionated AI config. One place that decides which model a call goes to, which login it runs under and what it may use, and refuses before anything is spent when a backend cannot serve the call.

Backends are a local or remote OpenAI-compatible endpoint, the Anthropic and Google APIs, and the `claude` command on a subscription login.

```
uv tool install -e 'moac/[api]'

moac profiles                         # what can be called, what serves it, whether it is up; where the config and the ledger are
moac up local                         # start what serves a profile (its `serve` unit) and wait for it
moac ledger                           # past calls per tool and profile: how many, how long, how many tokens
moac ask local --image f.png --raw "..."  # a picture with the prompt, to a local model that takes images
moac ask opus --raw "..."             # one captured call
moac run --interactive opux           # a claude session on a profile
moac login personal                   # sign a second account in
moac run --interactive --account personal opux
moac who                              # accounts, plans, login expiry
moac usage --watch                    # usage windows of every signed-in account
```

Design and internals: [AGENTS.md](AGENTS.md).
