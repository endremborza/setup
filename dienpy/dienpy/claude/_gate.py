"""Headroom decision over usage windows: which model may start now, else when to look again.

A scoped weekly window (e.g. Fable's) applies to a model whose id carries that scope's
name; session and all-model windows apply to every model. The session window is
judged against what the job will consume (`need`), the weekly ones against a ceiling.
"""

import datetime
from dataclasses import dataclass

from .usage import Window


@dataclass(frozen=True)
class Thresholds:
    session: float = 97.0  # ceiling for session.percent + need
    weekly: float = 97.0
    scoped: float = 97.0

    def limit(self, w: Window) -> float:
        if w.kind == "session":
            return self.session
        return self.scoped if w.model else self.weekly


@dataclass(frozen=True)
class Verdict:
    model: str = ""  # chosen model id, "" when every candidate is blocked
    blockers: tuple[Window, ...] = ()

    @property
    def wake_at(self) -> datetime.datetime | None:
        resets = [w.resets_at for w in self.blockers if w.resets_at]
        return min(resets) if resets else None


def applies(w: Window, model: str) -> bool:
    return not w.model or w.model.lower() in model.lower()


def load(w: Window, need: float) -> float:
    return w.percent + need if w.kind == "session" else w.percent


def blockers(windows: list[Window], model: str, t: Thresholds, need: float = 0.0) -> list[Window]:
    return [w for w in windows if applies(w, model) and load(w, need) >= t.limit(w)]


def pick(windows: list[Window], models: list[str], t: Thresholds, need: float = 0.0) -> Verdict:
    """First model in preference order with no blocking window; otherwise the union of blockers."""
    blocked: list[Window] = []
    for model in models:
        b = blockers(windows, model, t, need)
        if not b:
            return Verdict(model=model)
        blocked += [w for w in b if w not in blocked]
    return Verdict(blockers=tuple(blocked))
