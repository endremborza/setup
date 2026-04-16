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


def check_binary(name: str) -> bool:
    return shutil.which(name, path=extended_env()["PATH"]) is not None


def apt_install(packages: list[str]) -> None:
    subprocess.run(["sudo", "apt-get", "install", "-y", *packages], check=True)


def cargo_install(crates: list[str]) -> None:
    subprocess.run(["cargo", "install", *crates], env=extended_env(), check=True)


def clone_gh(owner: str, repo: str, tag: str) -> Path:
    dest = ONSET_PATH / repo
    if dest.exists():
        shutil.rmtree(dest)
    ONSET_PATH.mkdir(parents=True, exist_ok=True)
    run_cmd(
        f"git clone --branch {tag} --depth 1 https://github.com/{owner}/{repo}",
        cwd=ONSET_PATH,
    )
    return dest


def write_system_file(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=path.suffix) as f:
        f.write(content)
        tmp = Path(f.name)
    try:
        subprocess.run(["sudo", "cp", str(tmp), str(path)], check=True)
    finally:
        tmp.unlink(missing_ok=True)


def append_to_profile(line: str) -> None:
    profile = Path.home() / ".profile"
    text = profile.read_text() if profile.exists() else ""
    if line not in text:
        profile.write_text(text + f"\n{line}\n")
