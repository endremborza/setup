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
        # Filter for standard x.y.z versions
        stable = [v for v in versions if len(v.split('.')) <= 3]
        return max(stable, key=lambda v: [int(x) for x in v.split('.')])

def main():
    up_sh = Path(__file__).parent.parent.parent / "bash-scripts" / "up.sh"
    content = up_sh.read_text()
    
    apps = {
        "lua": (r'lua-([0-9.]+)', "lua"),
        "luarocks": (r'luarocks-([0-9.]+)', "luarocks/luarocks"),
        "jq": (r'jq jq-([0-9.]+)', "jqlang/jq"),
        "neovim": (r'neovim neovim (v[0-9.]+)', "neovim/neovim"),
        "fzf": (r'fzf (v[0-9.]+)', "junegunn/fzf"),
        "tmux": (r'tmux tmux ([0-9.]+)', "tmux/tmux"),
    }

    for name, (pat, src) in apps.items():
        curr = re.search(pat, content).group(1)
        lat = get_latest_lua() if src == "lua" else get_latest_gh(src)
        
        # Normalize for comparison
        c_norm = curr.lstrip('v').split('-')[-1]
        l_norm = lat.lstrip('v').split('-')[-1]
        star = "*" if c_norm != l_norm else " "
        
        print(f"{name:10} {curr:10} -> {lat:12} {star}")

if __name__ == "__main__":
    main()
