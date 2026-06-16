from __future__ import annotations

import json

from app import youtube


def test_ytdlp_metadata_uses_configured_cli_and_reads_thumbnail(monkeypatch) -> None:
    commands: list[list[str]] = []

    class Completed:
        stdout = json.dumps(
            {
                "id": "abc123",
                "title": "AI interview",
                "description": "A conversation about AI.",
                "webpage_url": "https://www.youtube.com/watch?v=abc123",
                "duration": 600,
                "channel": "Demo Channel",
                "uploader": "Demo Channel",
                "thumbnail": "https://i.ytimg.com/vi/abc123/maxresdefault.jpg",
                "timestamp": 1781092818,
                "upload_date": "20260610",
                "view_count": 1234,
            }
        )

    def fake_run(command: list[str], **_: object) -> Completed:
        commands.append(command)
        return Completed()

    monkeypatch.setattr(youtube, "_ytdlp_command", lambda: ["/custom/yt-dlp"])
    monkeypatch.setattr(youtube.subprocess, "run", fake_run)

    metadata = youtube._metadata_from_ytdlp_url("https://www.youtube.com/watch?v=abc123")

    assert metadata is not None
    assert metadata["thumbnail"].endswith("maxresdefault.jpg")
    assert metadata["upload_date"] == "20260610"
    assert commands[0][:3] == ["/custom/yt-dlp", "--ignore-config", "--dump-single-json"]
