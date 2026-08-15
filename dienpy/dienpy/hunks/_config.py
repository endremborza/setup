"""Shared config vocabulary: the three analysis dimensions and token classification."""

from dataclasses import dataclass

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

MODELS = ["haiku", "sonnet", "opus", "fable"]

DEFAULT = {"granularity": "normal", "model": "sonnet", "context": "bare"}


@dataclass(frozen=True)
class Config:
    granularity: str
    model: str
    context: str

    @property
    def key(self) -> str:
        return f"{self.granularity}|{self.model}|{self.context}"


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
    merged = {**DEFAULT, **(last or {}), **classify(dims)}
    config = Config(merged["granularity"], merged["model"], merged["context"])
    if config.granularity not in GRANULARITIES or config.context not in CONTEXTS:
        raise SystemExit(f"invalid config: {config.key}")
    return config
