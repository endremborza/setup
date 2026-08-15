"""Claude API auth and usage tracking."""

from protocli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.claude", prog="dienpy claude")
