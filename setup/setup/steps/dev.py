import subprocess
from pathlib import Path

from setup.runner import step
from setup.util import cargo_install, clone_gh, run_cmd, extended_env, ONSET_PATH
from setup.versions import get as _v

_LUA_VERSION = _v("lua")
_LUAROCKS_VERSION = _v("luarocks")
_JQ_TAG = _v("jq")
_NEOVIM_TAG = _v("neovim")
_FZF_TAG = _v("fzf")
_TMUX_TAG = _v("tmux")

# (crate, binary-check) — add a tool here and install + verify both update automatically
_CARGO_TOOLS: list[tuple[str, str]] = [
    ("ripgrep", "rg --version"),
    ("du-dust", "dust --version"),
    ("fd-find", "fd --version"),
    ("bat", "bat --version"),
    ("tree-sitter-cli", "tree-sitter --version"),
]


@step(
    profile="dev",
    name="tectonic",
    check="tectonic --version",
    verify="tectonic --version",
)
def install_tectonic() -> None:
    run_cmd(
        "sh -c 'curl --proto \"=https\" --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh'"
    )
    tectonic = Path("tectonic")
    if tectonic.exists():
        dest = Path.home() / ".local/bin/tectonic"
        dest.parent.mkdir(parents=True, exist_ok=True)
        tectonic.rename(dest)


@step(
    profile="shell",
    name="cargo-tools",
    check="rg --version",
    verify=" && ".join(cmd for _, cmd in _CARGO_TOOLS),
)
def install_cargo_tools() -> None:
    cargo_install([crate for crate, _ in _CARGO_TOOLS])


@step(profile="shell", name="nushell", check="nu --version", verify="nu --version")
def install_nushell() -> None:
    run_cmd("cargo install nu --locked", env=extended_env())


@step(profile="shell", name="lua", check="lua -v", verify="lua -v")
def install_lua() -> None:
    ONSET_PATH.mkdir(parents=True, exist_ok=True)
    run_cmd(
        f"sh -c 'curl -ROL http://www.lua.org/ftp/lua-{_LUA_VERSION}.tar.gz"
        f" && tar -zxf lua-{_LUA_VERSION}.tar.gz'",
        cwd=ONSET_PATH,
    )
    src = ONSET_PATH / f"lua-{_LUA_VERSION}"
    run_cmd("make linux test", cwd=src)
    run_cmd("sudo make install", cwd=src)


@step(
    profile="shell",
    name="luarocks",
    check="luarocks --version",
    verify="luarocks --version",
)
def install_luarocks() -> None:
    ONSET_PATH.mkdir(parents=True, exist_ok=True)
    run_cmd(
        f"sh -c 'curl -ROL http://luarocks.github.io/luarocks/releases/luarocks-{_LUAROCKS_VERSION}.tar.gz"
        f" && tar -zxf luarocks-{_LUAROCKS_VERSION}.tar.gz'",
        cwd=ONSET_PATH,
    )
    src = ONSET_PATH / f"luarocks-{_LUAROCKS_VERSION}"
    run_cmd("./configure --with-lua-include=/usr/local/include", cwd=src)
    run_cmd("make", cwd=src)
    run_cmd("sudo make install", cwd=src)


@step(profile="shell", name="jq", check="jq --version", verify="jq --version")
def install_jq() -> None:
    dest = clone_gh("jqlang", "jq", _JQ_TAG)
    run_cmd("git submodule update --init", cwd=dest)
    run_cmd("autoreconf -i", cwd=dest)
    run_cmd("./configure --with-oniguruma=builtin", cwd=dest)
    run_cmd("make clean", cwd=dest)
    run_cmd("make -j8", cwd=dest)
    run_cmd("sudo make install", cwd=dest)
    run_cmd("sudo ldconfig")


@step(profile="shell", name="sc-im", check="sc-im --version", verify="sc-im --version")
def install_scim() -> None:
    dest = clone_gh("andmarti1424", "sc-im", "main")
    run_cmd("make -C src", cwd=dest)
    bin_dir = Path.home() / ".local/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    link = bin_dir / "sc-im"
    link.unlink(missing_ok=True)
    link.symlink_to(dest / "src/sc-im")


@step(profile="shell", name="neovim", check="nvim --version", verify="nvim --version")
def install_neovim() -> None:
    dest = clone_gh("neovim", "neovim", _NEOVIM_TAG)
    run_cmd("make CMAKE_BUILD_TYPE=RelWithDebInfo", cwd=dest)
    run_cmd("sudo make install", cwd=dest)


@step(profile="shell", name="fzf", check="fzf --version", verify="fzf --version")
def install_fzf() -> None:
    dest = clone_gh("junegunn", "fzf", _FZF_TAG)
    run_cmd("./install --all --key-bindings --completion --update-rc", cwd=dest)
    bin_dir = Path.home() / ".local/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(f"stow --verbose=3 -t {bin_dir} bin", cwd=dest)


@step(profile="shell", name="tmux", check="tmux -V", verify="tmux -V")
def install_tmux() -> None:
    dest = clone_gh("tmux", "tmux", _TMUX_TAG)
    run_cmd("sh autogen.sh", cwd=dest)
    run_cmd("./configure", cwd=dest)
    run_cmd("sudo make install", cwd=dest)


@step(profile="dev", name="node", check="node --version", verify="node --version")
def install_node() -> None:
    run_cmd(
        "sh -c 'curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash'"
    )
    nvm_dir = Path.home() / ".nvm"
    nvm_env = {**extended_env(), "NVM_DIR": str(nvm_dir)}
    run_cmd(f"sh -c '. {nvm_dir}/nvm.sh && nvm install node'", env=nvm_env)
    # nvm installs node outside the system PATH; symlink into ~/.local/bin so it's always available
    result = subprocess.run(
        f"sh -c '. {nvm_dir}/nvm.sh && command -v node'",
        shell=True,
        capture_output=True,
        text=True,
        env=nvm_env,
    )
    if result.returncode == 0:
        node_bin = Path(result.stdout.strip())
        link = Path.home() / ".local/bin" / "node"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.unlink(missing_ok=True)
        link.symlink_to(node_bin)
