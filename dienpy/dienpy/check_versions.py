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
        versions = re.findall(r'lua-([0-9.]+)\.tar\.gz', content)
        return max(versions, key=lambda v: [int(x) for x in v.split('.')])

def main():
    up_sh = Path(__file__).parent.parent.parent / "bash-scripts" / "up.sh"
    content = up_sh.read_text()
    
    current = {
        "lua": re.search(r'lua-([0-9.]+)', content).group(1),
        "luarocks": re.search(r'luarocks-([0-9.]+)', content).group(1),
        "jq": re.search(r'jq jq-([0-9.]+)', content).group(1),
        "neovim": re.search(r'neovim neovim (v[0-9.]+)', content).group(1),
        "fzf": re.search(r'fzf (v[0-9.]+)', content).group(1),
        "tmux": re.search(r'tmux tmux ([0-9.]+)', content).group(1),
    }

    latest = {
        "lua": get_latest_lua(),
        "luarocks": get_latest_gh("luarocks/luarocks"),
        "jq": get_latest_gh("jqlang/jq"),
        "neovim": get_latest_gh("neovim/neovim"),
        "fzf": get_latest_gh("junegunn/fzf"),
        "tmux": get_latest_gh("tmux/tmux"),
    }

    print(f"{'App':<10} {'Current':<12} {'Latest':<12}")
    for app in current:
        c, l = current[app], latest[app]
        star = "*" if c != l.lstrip('v') and c.lstrip('v') != l.lstrip('v') else " "
        print(f"{app:<10} {c:<12} {l:<12} {star}")

if __name__ == "__main__":
    main()
