"""Shared config vocabulary: the three analysis dimensions and token classification."""

from dataclasses import dataclass
from typing import Annotated

from protocli import Complete

from .. import ai

GRANULARITIES = {
    "loose": "broad thematic groups; a feature together with its tests, docs and "
    "mechanical fallout is one group",
    "normal": "conventional atomic commits; independent concerns are separate groups, "
    "mechanical fallout stays with the change that caused it",
    "granular": "smallest self-consistent units; separate refactoring from behavior "
    "changes, separate independent tweaks even within one file",
}

CONTEXTS = {
    "bare": "hunks only, no project context",
    "agents": "AGENTS.md included as project context",
    "explore": "AGENTS.md included, agent may read repo files before grouping",
}

DEFAULT = {"granularity": "normal", "context": "bare"}


@dataclass(frozen=True)
class Config:
    granularity: str
    model: (
        str  # an ai profile name; unknown names fall through as bare claude CLI models
    )
    context: str

    @property
    def key(self) -> str:
        return f"{self.granularity}|{self.model}|{self.context}"


def tokens() -> list[str]:
    return [*GRANULARITIES, *CONTEXTS, *ai.profile_names()]


Dim = Annotated[str, Complete(tokens)]


def classify(dims: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for d in dims:
        if d in GRANULARITIES:
            out["granularity"] = d
        elif d in CONTEXTS:
            out["context"] = d
        else:
            out["model"] = d
    return out


def resolve(dims: tuple[str, ...], last: dict | None) -> Config:
    merged = {
        **DEFAULT,
        "model": ai.profile_for_tool("hunks"),
        **(last or {}),
        **classify(dims),
    }
    config = Config(merged["granularity"], merged["model"], merged["context"])
    if config.granularity not in GRANULARITIES or config.context not in CONTEXTS:
        raise SystemExit(f"invalid config: {config.key}")
    return config
