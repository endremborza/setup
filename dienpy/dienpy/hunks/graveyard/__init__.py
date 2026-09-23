"""The graveyard: buried patches and stashed leftovers — list, restore or drop them."""

from protocli import Dispatcher

_dispatcher = Dispatcher.from_package(
    "dienpy.hunks.graveyard", prog="dienpy hunks graveyard"
)
