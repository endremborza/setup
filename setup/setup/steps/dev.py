from __future__ import annotations

from pathlib import Path

from setup.runner import step
from setup.util import cargo_install, clone_gh, run_cmd, extended_env, ONSET_PATH

_LUA_VERSION = "5.5.0"
_LUAROCKS_VERSION = "3.13.0"
_JQ_TAG = "jq-1.8.1"
_NEOVIM_TAG = "v0.11.6"
_FZF_TAG = "v0.67.0"
_TMUX_TAG = "3.6a"

_CARGO_TOOLS = ["ripgrep", "du-dust", "fd-find", "bat", "tree-sitter-cli"]


@step(level=1, name="tectonic", check="tectonic --version")
def install_tectonic() -> None:
    run_cmd(
        "sh -c 'curl --proto \"=https\" --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh'"
    )
    tectonic = Path("tectonic")
    if tectonic.exists():
        dest = Path.home() / ".local/bin/tectonic"
        dest.parent.mkdir(parents=True, exist_ok=True)
        tectonic.rename(dest)


@step(level=1, name="cargo-tools", check="rg --version")
def install_cargo_tools() -> None:
    cargo_install(_CARGO_TOOLS)


@step(level=1, name="nushell", check="nu --version")
def install_nushell() -> None:
    run_cmd("cargo install nu --locked", env=extended_env())


@step(level=1, name="lua", check="lua -v")
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


@step(level=1, name="luarocks", check="luarocks --version")
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


@step(level=1, name="jq", check="jq --version")
def install_jq() -> None:
    dest = clone_gh("jqlang", "jq", _JQ_TAG)
    run_cmd("git submodule update --init", cwd=dest)
    run_cmd("autoreconf -i", cwd=dest)
    run_cmd("./configure --with-oniguruma=builtin", cwd=dest)
    run_cmd("make clean && make -j8", cwd=dest)
    run_cmd("sudo make install", cwd=dest)


@step(level=1, name="sc-im", check="sc-im --version")
def install_scim() -> None:
    dest = clone_gh("andmarti1424", "sc-im", "main")
    # make -C src
    # ln -s /home/borza/onset-src/sc-im/src/sc-im ~/.local/bin/


@step(level=1, name="neovim", check="nvim --version")
def install_neovim() -> None:
    dest = clone_gh("neovim", "neovim", _NEOVIM_TAG)
    run_cmd("make CMAKE_BUILD_TYPE=RelWithDebInfo", cwd=dest)
    run_cmd("sudo make install", cwd=dest)


@step(level=1, name="fzf", check="fzf --version")
def install_fzf() -> None:
    dest = clone_gh("junegunn", "fzf", _FZF_TAG)
    run_cmd("./install --all --key-bindings --completion --update-rc", cwd=dest)
    bin_dir = Path.home() / ".local/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    run_cmd(f"stow --verbose=3 -t {bin_dir} bin", cwd=dest)


@step(level=1, name="tmux", check="tmux -V")
def install_tmux() -> None:
    dest = clone_gh("tmux", "tmux", _TMUX_TAG)
    run_cmd("sh autogen.sh", cwd=dest)
    run_cmd("./configure", cwd=dest)
    run_cmd("sudo make install", cwd=dest)


@step(level=1, name="node", check="node --version")
def install_node() -> None:
    run_cmd(
        "sh -c 'curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh | bash'"
    )
    nvm_dir = Path.home() / ".nvm"
    run_cmd(
        f"sh -c '. {nvm_dir}/nvm.sh && nvm install node'",
        env={**extended_env(), "NVM_DIR": str(nvm_dir)},
    )
