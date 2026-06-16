from __future__ import annotations

from app import bilibili, youtube


class Completed:
    stdout = "[]"


def test_bilibili_discovery_uses_foreground_window(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> Completed:
        commands.append(command)
        return Completed()

    monkeypatch.setenv("OPENCLI_WINDOW_MODE", "foreground")
    monkeypatch.setenv("OPENCLI_PREFLIGHT_ENABLED", "false")
    monkeypatch.setattr(bilibili.subprocess, "run", fake_run)

    assert bilibili._run_opencli_search("opencli", "AI 采访", 1) == []
    assert bilibili._run_opencli_user_videos("opencli", "280780745", 1) == []
    assert all(command[-2:] == ["--window", "foreground"] for command in commands)


def test_youtube_discovery_uses_foreground_window(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> Completed:
        commands.append(command)
        return Completed()

    monkeypatch.setenv("OPENCLI_WINDOW_MODE", "foreground")
    monkeypatch.setenv("OPENCLI_PREFLIGHT_ENABLED", "false")
    monkeypatch.setattr(youtube.subprocess, "run", fake_run)

    assert youtube._run_opencli_youtube_search("opencli", "AI interview", 1) == []
    assert commands[0][-2:] == ["--window", "foreground"]
