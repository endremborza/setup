"""Download kokoro-onnx model files to ~/.local/share/kokoro/."""

from ._core import MODEL_BASE_URL, MODEL_DIR, MODEL_PATH, VOICES_PATH


def main() -> None:
    import requests
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    files = [("kokoro-v1.0.onnx", MODEL_PATH), ("voices-v1.0.bin", VOICES_PATH)]

    with Progress(
        TextColumn("[bold blue]{task.fields[name]}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        for name, dest in files:
            if dest.exists():
                print(f"{name}: already present")
                continue
            url = f"{MODEL_BASE_URL}/{name}"
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0)) or None
            task = progress.add_task("dl", name=name, total=total)
            with dest.open("wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))
