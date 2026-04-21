"""Generate random project names."""
import json
import random
from pathlib import Path

from .constants import ASSETS_DIR

proot = ASSETS_DIR / "values"


def get_name(s=None):
    us_states = json.loads((proot / "us-states.json").read_text())
    cities = json.loads((proot / "cities.json").read_text())
    countries = json.loads((proot / "countries.json").read_text())
    adjectives = json.loads((proot / "adjectives.json").read_text())
    base_colors = json.loads((proot / "colors.json").read_text())
    animals = json.loads((proot / "animals.json").read_text())
    items = json.loads((proot / "household-items.json").read_text())
    p1 = adjectives + base_colors
    p2 = animals + items
    p3 = us_states + cities + countries
    rng = random.Random(s)
    return f"{rng.choice(p1)} {rng.choice(p2)} of {rng.choice(p3)}"


def main():
    print(get_name())


if __name__ == "__main__":
    main()
