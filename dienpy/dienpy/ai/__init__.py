"""AI backend layer: capability-checked profiles over openai/api/cli transports."""

from protocli import Dispatcher

from ._backend import EFFORTS, Api, Backend, Cli, Effort, Need, Openai, resolve
from ._profiles import ProfileName
from ._profiles import for_tool as profile_for_tool
from ._profiles import names as profile_names
from ._transport import send

__all__ = [
    "EFFORTS",
    "Api",
    "Backend",
    "Cli",
    "Effort",
    "Need",
    "Openai",
    "profile_for_tool",
    "ProfileName",
    "profile_names",
    "resolve",
    "send",
]

_dispatcher = Dispatcher.from_package("dienpy.ai", prog="dienpy ai")
