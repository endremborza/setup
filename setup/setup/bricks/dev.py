import subprocess
from pathlib import Path

from setup.runner import brick
from setup.util import (
    ONSET_PATH,
    cargo_install,
    clone_gh,
    extended_env,
    fetch,
    link_bin,
    pinned_check,
    run_cmd,
    run_shell,
    sudo_make_install,
)
from setup.versions import get as _v
from setup.versions import number

_LUA_VERSION = number(_v("lua"))
_LUAROCKS_VERSION = number(_v("luarocks"))
_JQ_TAG = _v("jq")
_NEOVIM_TAG = _v("neovim")
_FZF_TAG = _v("fzf")
_TMUX_TAG = _v("tmux")
_TPM_TAG = _v("tpm")
_NVM_TAG = _v("nvm")
_BUN_TAG = _v("bun")
_TECTONIC_VERSION = number(_v("tectonic"))

# (crate, binary-check) — add a tool here and install + verify both update automatically
_CARGO_TOOLS: list[tuple[str, str]] = [
    ("ripgrep", "rg --version"),
    ("du-dust", "dust --version"),
    ("fd-find", "fd --version"),
    ("bat", "bat --version"),
    ("tree-sitter-cli", "tree-sitter --version"),
]

# musl build: static, works on any glibc.
_TECTONIC_URL = (
    "https://github.com/tectonic-typesetting/tectonic/releases/download/"
    f"tectonic%40{_TECTONIC_VERSION}/"
    f"tectonic-{_TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz"
)


@brick(
    profile="dev",
    name="tectonic",
    check=pinned_check("tectonic --version", _TECTONIC_VERSION),
)
def install_tectonic() -> None:
    dest = ONSET_PATH / f"tectonic-{_TECTONIC_VERSION}"
    fetch(_TECTONIC_URL, dest)
    link_bin(dest / "tectonic")


_CARGO_TOOLS_CHECK = " && ".join(cmd for _, cmd in _CARGO_TOOLS)


@brick(profile="shell", name="cargo-tools", check=_CARGO_TOOLS_CHECK)
def install_cargo_tools() -> None:
    cargo_install([crate for crate, _ in _CARGO_TOOLS])


# tmux pane-layout commands bound in .tmux.conf and leftwm's config.ron.
@brick(profile="shell", name="tmuxwrap", check="command -v tmuxwrap")
def install_tmuxwrap() -> None:
    run_cmd(
        "uv tool install git+https://github.com/endremborza/tmuxwrap",
        env=extended_env(),
    )


@brick(profile="shell", name="lua", check=pinned_check("lua -v", _LUA_VERSION))
def install_lua() -> None:
    fetch(f"https://www.lua.org/ftp/lua-{_LUA_VERSION}.tar.gz", ONSET_PATH)
    src = ONSET_PATH / f"lua-{_LUA_VERSION}"
    run_cmd("make linux test", cwd=src)
    sudo_make_install(src)


@brick(
    profile="shell",
    name="luarocks",
    check=pinned_check("luarocks --version", _LUAROCKS_VERSION),
)
def install_luarocks() -> None:
    fetch(
        "https://luarocks.github.io/luarocks/releases/"
        f"luarocks-{_LUAROCKS_VERSION}.tar.gz",
        ONSET_PATH,
    )
    src = ONSET_PATH / f"luarocks-{_LUAROCKS_VERSION}"
    run_cmd("./configure --with-lua-include=/usr/local/include", cwd=src)
    run_cmd("make", cwd=src)
    sudo_make_install(src)


@brick(profile="shell", name="jq", check=pinned_check("jq --version", _JQ_TAG))
def install_jq() -> None:
    dest = clone_gh("jqlang", "jq", _JQ_TAG)
    run_cmd("git submodule update --init", cwd=dest)
    run_cmd("autoreconf -i", cwd=dest)
    run_cmd("./configure --with-oniguruma=builtin", cwd=dest)
    run_cmd("make clean", cwd=dest)
    run_cmd("make -j8", cwd=dest)
    sudo_make_install(dest)
    run_cmd("sudo ldconfig")


# sc-im --version exits nonzero; grep the banner instead. Never `grep -q`
# here: the early pipe close leaves sc-im blocked on SIGPIPE under capture.
_SCIM_CHECK = "sc-im --version 2>&1 | grep 'sc-im - version'"


@brick(profile="shell", name="sc-im", check=_SCIM_CHECK)
def install_scim() -> None:
    dest = clone_gh("andmarti1424", "sc-im", "main")
    run_cmd("make -C src", cwd=dest)
    link_bin(dest / "src/sc-im")


@brick(
    profile="shell", name="neovim", check=pinned_check("nvim --version", _NEOVIM_TAG)
)
def install_neovim() -> None:
    dest = clone_gh("neovim", "neovim", _NEOVIM_TAG)
    build = "make CMAKE_BUILD_TYPE=RelWithDebInfo"
    try:
        run_cmd(build, cwd=dest)
    except subprocess.CalledProcessError:
        # a build tree left by another tag can hold stale cmake/deps state
        run_cmd("make distclean", cwd=dest)
        run_cmd(build, cwd=dest)
    sudo_make_install(dest)


@brick(profile="shell", name="fzf", check=pinned_check("fzf --version", _FZF_TAG))
def install_fzf() -> None:
    dest = clone_gh("junegunn", "fzf", _FZF_TAG)
    run_cmd("./install --all --key-bindings --completion --update-rc", cwd=dest)
    for name in ("fzf", "fzf-tmux", "fzf-preview.sh"):
        link_bin(dest / "bin" / name)


@brick(profile="shell", name="tmux", check=pinned_check("tmux -V", _TMUX_TAG))
def install_tmux() -> None:
    dest = clone_gh("tmux", "tmux", _TMUX_TAG)
    run_cmd("sh autogen.sh", cwd=dest)
    run_cmd("./configure", cwd=dest)
    sudo_make_install(dest)


_TPM_LINK = Path.home() / ".tmux/plugins/tpm"


# .tmux.conf runs tpm from ~/.tmux/plugins/tpm, where tpm also clones the
# plugins it manages, so the link lives there rather than under ~/.local/bin.
@brick(
    profile="shell",
    name="tpm",
    check=f"test -x {_TPM_LINK}/tpm && "
    + pinned_check(f"git -C {_TPM_LINK} describe --tags --exact-match", _TPM_TAG),
)
def install_tpm() -> None:
    dest = clone_gh("tmux-plugins", "tpm", _TPM_TAG)
    _TPM_LINK.parent.mkdir(parents=True, exist_ok=True)
    _TPM_LINK.unlink(missing_ok=True)
    _TPM_LINK.symlink_to(dest)


@brick(profile="dev", name="node", check="node --version && npm --version")
def install_node() -> None:
    nvm_dir = Path.home() / ".nvm"
    nvm_env = {**extended_env(), "NVM_DIR": str(nvm_dir)}
    run_shell(
        "curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/"
        f"{_NVM_TAG}/install.sh | bash",
        env=nvm_env,
    )
    run_shell(f". {nvm_dir}/nvm.sh && nvm install node", env=nvm_env)
    # nvm keeps node outside the system PATH; link the binaries into ~/.local/bin
    node_bin = subprocess.run(
        ["bash", "-c", f". {nvm_dir}/nvm.sh && command -v node"],
        capture_output=True,
        text=True,
        check=True,
        env=nvm_env,
    ).stdout.strip()
    for name in ("node", "npm", "npx"):
        link_bin(Path(node_bin).parent / name)


@brick(profile="dev", name="bun", check=pinned_check("bun --version", _BUN_TAG))
def install_bun() -> None:
    run_shell(f"curl -fsSL https://bun.sh/install | bash -s {_BUN_TAG}")
