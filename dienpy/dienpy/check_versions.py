import re
import urllib.request
import json
from pathlib import Path


def get_latest_gh(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            return data["tag_name"]
    except Exception:
        url = f"https://api.github.com/repos/{repo}/tags"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            return data[0]["name"]


def get_latest_lua():
    url = "http://www.lua.org/ftp/"
    with urllib.request.urlopen(url) as response:
        content = response.read().decode()
        versions = re.findall(r"lua-([0-9.]+)\.tar\.gz", content)
        # Filter for standard x.y.z versions
        stable = [v for v in versions if len(v.split(".")) <= 3]
        return max(stable, key=lambda v: [int(x) for x in v.split(".")])


def main():
    from dienpy.cli import handle_help

    if handle_help(
        "dienpy check_versions", "Check upstream versions of tracked dev tools."
    ):
        return
    up_sh = Path(__file__).parent.parent.parent / "bash-scripts" / "up.sh"
    content = up_sh.read_text()
    new_content = content

    apps = {
        "lua": (r"lua-([0-9.]+)", "lua"),
        "luarocks": (r"luarocks-([0-9.]+)", "luarocks/luarocks"),
        "jq": (r"jq jq-([0-9.]+)", "jqlang/jq"),
        "neovim": (r"neovim neovim (v[0-9.]+)", "neovim/neovim"),
        "fzf": (r"fzf (v[0-9.]+)", "junegunn/fzf"),
        "tmux": (r"tmux tmux ([0-9.]+)", "tmux/tmux"),
    }

    print(f"{'App':<10} {'Current':<12} {'Latest':<12} {'Status'}")
    for name, (pat, src) in apps.items():
        match = re.search(pat, content)
        if not match:
            continue

        curr = match.group(1)
        lat = get_latest_lua() if src == "lua" else get_latest_gh(src)

        # Strip prefixes for normalization and selection
        # We want to keep the format already present in up.sh
        if name == "luarocks":
            lat = lat.lstrip("v")
        elif name == "jq":
            lat = lat.replace("jq-", "")

        c_norm = curr.lstrip("v")
        l_norm = lat.lstrip("v")

        if c_norm != l_norm:
            old_str = match.group(0)
            new_str = old_str.replace(curr, lat)
            new_content = new_content.replace(old_str, new_str)
            status = f"UPDATING ({curr} -> {lat})"
        else:
            status = "OK"

        print(f"{name:<10} {curr:<12} {lat:<12} {status}")

    if new_content != content:
        up_sh.write_text(new_content)
        print("\nChanges saved to up.sh")


if __name__ == "__main__":
    main()
