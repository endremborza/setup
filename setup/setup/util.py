import getpass
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

ONSET_PATH = Path.home() / "onset-src"


def extended_env() -> dict[str, str]:
    env = os.environ.copy()
    extra = [
        str(Path.home() / ".cargo/bin"),
        str(Path.home() / ".local/bin"),
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


def clone_gh(owner: str, repo: str, tag: str) -> Path:
    dest = ONSET_PATH / repo
    if dest.exists():
        _clear(dest)
    ONSET_PATH.mkdir(parents=True, exist_ok=True)
    run_cmd(
        f"git clone --branch {tag} --depth 1 https://github.com/{owner}/{repo}",
        cwd=ONSET_PATH,
    )
    return dest


def write_system_file(path: Path, content: str, mode: str = "644") -> None:
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=path.suffix) as f:
        f.write(content)
        tmp = Path(f.name)
    try:
        # install, not cp: the tempfile's 600 must not become the target mode
        subprocess.run(["sudo", "install", "-m", mode, str(tmp), str(path)], check=True)
    finally:
        tmp.unlink(missing_ok=True)


def append_to_profile(line: str) -> None:
    profile = Path.home() / ".profile"
    text = profile.read_text() if profile.exists() else ""
    if line not in text:
        profile.write_text(text + f"\n{line}\n")
