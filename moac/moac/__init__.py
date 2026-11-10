"""Models, options, accounts and capabilities: my opinionated AI config."""

__version__ = "0.1.0"

from protocli import Dispatcher

from ._account import Account, AccountName
from ._backend import EFFORTS, Api, Backend, Cli, Effort, Need, Openai, resolve
from ._profiles import ProfileName
from ._profiles import bindings as profile_bindings
from ._profiles import for_tool as profile_for_tool
from ._profiles import names as profile_names
from ._stream import Outcome
from ._transport import TIMEOUT, launch, send, supervise

__all__ = [
    "EFFORTS",
    "Account",
    "AccountName",
    "Api",
    "Backend",
    "Cli",
    "Effort",
    "Need",
    "Openai",
    "Outcome",
    "TIMEOUT",
    "launch",
    "profile_bindings",
    "profile_for_tool",
    "ProfileName",
    "profile_names",
    "resolve",
    "send",
    "supervise",
]

_dispatcher = Dispatcher.from_package("moac")
