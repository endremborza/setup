"""nvim tooling: verify LSP health, commit config, fetch release notes."""

from protocli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.nvim", prog="dienpy nvim")
