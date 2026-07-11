from __future__ import annotations

from app import ytdlp_runtime


class Completed:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_ytdlp_runtime_uses_configured_path_for_command_and_status(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setenv("YTDLP_PATH", "yt-dlp-custom")
    monkeypatch.setattr(ytdlp_runtime.shutil, "which", lambda name: "/usr/local/bin/yt-dlp-custom" if name == "yt-dlp-custom" else None)
    monkeypatch.setattr(
        ytdlp_runtime.subprocess,
        "run",
        lambda command, **_: calls.append(command) or Completed(stdout="2026.07.04\n"),
    )

    assert ytdlp_runtime.ytdlp_command() == ["/usr/local/bin/yt-dlp-custom"]
    assert ytdlp_runtime.ytdlp_status() == (True, "/usr/local/bin/yt-dlp-custom (2026.07.04)")
    assert calls == [["/usr/local/bin/yt-dlp-custom", "--version"]]


def test_ytdlp_runtime_falls_back_to_installed_python_module(monkeypatch) -> None:
    monkeypatch.setenv("YTDLP_PATH", "missing-yt-dlp")
    monkeypatch.setattr(ytdlp_runtime.shutil, "which", lambda _: None)
    monkeypatch.setattr(ytdlp_runtime.Path, "is_file", lambda _: False)
    monkeypatch.setattr(ytdlp_runtime.importlib.util, "find_spec", lambda name: object() if name == "yt_dlp" else None)

    assert ytdlp_runtime.ytdlp_command() == [ytdlp_runtime.sys.executable, "-m", "yt_dlp"]
