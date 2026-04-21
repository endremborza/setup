"""AI commit messages, model listing, and response caching."""
from dienpy.cli import Dispatcher

_dispatcher = Dispatcher.from_package("dienpy.ai", prog="dienpy ai")
