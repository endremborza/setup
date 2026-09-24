import getpass
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from setup.versions import number

ONSET_PATH = Path.home() / "onset-src"
BIN_DIR = Path.home() / ".local/bin"


def extended_env() -> dict[str, str]:
    env = os.environ.copy()
    extra = [
        str(Path.home() / ".cargo/bin"),
        str(Path.home() / ".bun/bin"),
        str(BIN_DIR),
        "/usr/local/bin",
    ]
    env["PATH"] = ":".join(extra + [env.get("PATH", "")])
    return env


def run_cmd(
    cmd: str, cwd: Path | None = None, env: dict[str, str] | None = None
) -> None:
    subprocess.run(
        shlex.split(cmd),
        cwd=cwd,
        env=env if env is not None else extended_env(),
        check=True,
    )


def run_shell(
    cmd: str, cwd: Path | None = None, env: dict[str, str] | None = None
) -> None:
    """A shell line with pipes; pipefail so a failed download never feeds an installer."""
    subprocess.run(
        ["bash", "-o", "pipefail", "-c", cmd],
        cwd=cwd,
        env=env if env is not None else extended_env(),
        check=True,
    )


def pinned_check(cmd: str, tag: str) -> str:
    """Passes only when `cmd` prints the pinned number: a bump fails the check on
    every machine, so the next run converges it. The matching line is printed,
    which is the version the verify report shows."""
    want = number(tag).replace(".", r"\.")
    return f"{cmd} 2>&1 | grep -E '(^|[^0-9.]){want}([^0-9.]|$)'"


def dpkg_check(*packages: str) -> str:
    """Passes only when every package is installed (`ii`); an unknown package
    surfaces as dpkg-query's error line, which fails the same way."""
    return (
        "! dpkg-query -W -f='${db:Status-Abbrev}\\n' "
        + " ".join(packages)
        + " 2>&1 | grep -qv '^ii'"
    )


def apt_install(packages: list[str]) -> None:
    subprocess.run(["sudo", "apt-get", "install", "-y", *packages], check=True)


def cargo_install(crates: list[str]) -> None:
    subprocess.run(["cargo", "install", *crates], env=extended_env(), check=True)


def sudo_make_install(cwd: Path) -> None:
    """`make install` needs root; the build tree must not end up owned by it.
    cmake writes its install manifest back into the tree as root, and a single
    root-owned file there is what makes the next `clone_gh` fail to clear it."""
    run_cmd("sudo make install", cwd=cwd)
    run_cmd(f"sudo chown -R {getpass.getuser()}: {cwd}")


def _clear(dest: Path) -> None:
    """Root-owned leftovers from an older install defeat a plain rmtree; clear
    them as root rather than stranding the brick that wants to rebuild."""
    try:
        shutil.rmtree(dest)
    except PermissionError:
        subprocess.run(["sudo", "rm", "-rf", str(dest)], check=True)


def _checkout(dest: Path, ref: str) -> None:
    """Move an existing clone to `ref` (tag or branch) keeping its build tree."""
    tag_fetch = subprocess.run(
        ["git", "fetch", "-q", "--depth", "1", "origin", "tag", ref],
        cwd=dest,
        check=False,
    )
    if tag_fetch.returncode:
        run_cmd(f"git fetch -q --depth 1 origin {ref}", cwd=dest)
    run_cmd("git checkout -q --detach FETCH_HEAD", cwd=dest)


def clone_gh(owner: str, repo: str, ref: str) -> Path:
    dest = ONSET_PATH / repo
    if (dest / ".git").is_dir():
        try:
            _checkout(dest, ref)
            return dest
        except subprocess.CalledProcessError:
            pass
    if dest.exists():
        _clear(dest)
    ONSET_PATH.mkdir(parents=True, exist_ok=True)
    run_cmd(
        f"git clone --branch {ref} --depth 1 https://github.com/{owner}/{repo}",
        cwd=ONSET_PATH,
    )
    return dest


def download(url: str, cwd: Path = ONSET_PATH) -> Path:
    cwd.mkdir(parents=True, exist_ok=True)
    run_cmd(f"curl -fsSLO {url}", cwd=cwd)
    return cwd / url.rsplit("/", 1)[1]


def fetch(url: str, dest: Path) -> Path:
    """Download into ONSET_PATH and unpack under `dest`; returns the archive."""
    archive = download(url)
    dest.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        run_cmd(f"unzip -oq {archive} -d {dest}")
    else:
        run_cmd(f"tar -xf {archive} -C {dest}")
    return archive


def link_bin(target: Path, name: str | None = None) -> Path:
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    link = BIN_DIR / (name or target.name)
    link.unlink(missing_ok=True)
    link.symlink_to(target)
    return link


def write_system_file(path: Path, content: str, mode: str = "644") -> None:
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=path.suffix) as f:
        f.write(content)
        tmp = Path(f.name)
    try:
        # install, not cp: the tempfile's 600 must not become the target mode
        subprocess.run(["sudo", "install", "-m", mode, str(tmp), str(path)], check=True)
    finally:
        tmp.unlink(missing_ok=True)
