from setup.versions import load


def main() -> None:
    vers = load()
    print(f"{'Tool':<14} {'Tag':<16} {'Source':<35} {'Checked'}")
    for tv in vers.values():
        print(f"{tv.name:<14} {tv.tag:<16} {tv.source:<35} {tv.checked}")
