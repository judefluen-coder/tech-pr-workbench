from __future__ import annotations

from app import opencli_runtime


class Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_opencli_preflight_opens_chrome_when_no_window(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> Result:
        calls.append(command)
        if command[:2] == ["pgrep", "-x"]:
            return Result(1)
        if command[:3] == ["opencli", "daemon", "status"]:
            return Result(0, "Daemon: running\nExtension: connected")
        return Result()

    monkeypatch.setenv("OPENCLI_WINDOW_MODE", "foreground")
    monkeypatch.setenv("OPENCLI_PREFLIGHT_ENABLED", "true")
    monkeypatch.setattr(opencli_runtime.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(opencli_runtime.shutil, "which", lambda name: "/usr/bin/open" if name == "open" else None)
    monkeypatch.setattr(opencli_runtime.subprocess, "run", fake_run)

    opencli_runtime.prepare_opencli_browser("opencli", "https://www.youtube.com")

    assert ["open", "-a", "Google Chrome", "https://www.youtube.com"] in calls


def test_opencli_preflight_wakes_bridge_when_extension_disconnected(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> Result:
        calls.append(command)
        if command[:2] == ["pgrep", "-x"]:
            return Result(0)
        if command[0] == "osascript":
            return Result(0, "1\n")
        if command[:3] == ["opencli", "daemon", "status"]:
            return Result(0, "Daemon: running\nExtension: disconnected")
        if command[:2] == ["opencli", "doctor"]:
            return Result(0, "[OK] Connectivity: connected")
        return Result()

    monkeypatch.setenv("OPENCLI_WINDOW_MODE", "foreground")
    monkeypatch.setenv("OPENCLI_PREFLIGHT_ENABLED", "true")
    monkeypatch.setattr(opencli_runtime.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(opencli_runtime.shutil, "which", lambda name: "/usr/bin/open" if name == "open" else None)
    monkeypatch.setattr(opencli_runtime.subprocess, "run", fake_run)

    opencli_runtime.prepare_opencli_browser("opencli", "https://www.bilibili.com")

    assert ["opencli", "doctor"] in calls
