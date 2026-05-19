"""nvim tooling: verify LSP health, commit config, fetch release notes."""

from dienpy.cli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.nvim", prog="dienpy nvim")
