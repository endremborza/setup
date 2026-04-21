"""Claude API auth and usage tracking."""
from dienpy.cli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.claude", prog="dienpy claude")
