import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def make_client() -> TestClient:
    tmp = tempfile.TemporaryDirectory()
    os.environ["TECH_PR_DB_PATH"] = str(Path(tmp.name) / "app.db")
    os.environ["TECH_PR_UPLOAD_DIR"] = str(Path(tmp.name) / "uploads")
    os.environ["TECH_PR_EXPORT_DIR"] = str(Path(tmp.name) / "exports")
    os.environ["TECH_PR_TMP_DIR"] = str(Path(tmp.name) / "tmp")
    os.environ["YOUTUBE_API_KEY"] = ""
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["CLOUD_AI_ENABLED"] = "false"
    os.environ["ARGOS_TRANSLATE_ENABLED"] = "false"
    os.environ["PLACEHOLDER_TRANSLATION_ENABLED"] = "true"
    os.environ["LOCAL_YTDLP_DISCOVERY"] = "false"
    os.environ["OPENCLI_DISCOVERY_ENABLED"] = "false"
    from app.main import app
    from app.db import init_db
    from app.seed import seed_people_if_empty

    init_db()
    seed_people_if_empty()

    client = TestClient(app)
    client.__dict__["_tmpdir"] = tmp
    return client


def test_demo_sync_does_not_download_public_youtube() -> None:
    client = make_client()
    response = client.post("/api/sync/youtube", json={"days_back": 1, "limit_per_query": 2})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "demo"
    videos = client.get("/api/videos").json()
    assert videos
    assert all(item["compliance_note"] == "metadata_only" for item in videos)


def test_daily_range_does_not_return_demo_or_search_urls_without_real_source() -> None:
    client = make_client()
    response = client.post("/api/daily/run", json={"start_date": "2026-06-01", "end_date": "2026-06-13", "limit_per_query": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["start_date"] == "2026-06-01"
    assert payload["end_date"] == "2026-06-13"
    assert payload["items"] == []


def test_import_transcribe_clip_and_export() -> None:
    client = make_client()
    client.post("/api/sync/youtube", json={})
    video_id = client.get("/api/videos").json()[0]["id"]

    import_response = client.post(
        "/api/media/import",
        data={
            "video_id": video_id,
            "authorization_note": "自有采访素材文本稿",
            "transcript_text": "This is a useful answer.\nWe should mark the product strategy quote.",
            "delete_after_processing": "true",
        },
    )
    assert import_response.status_code == 200
    assert import_response.json()["kind"] == "transcript"

    transcribe_response = client.post(f"/api/videos/{video_id}/transcribe")
    assert transcribe_response.status_code == 200
    assert transcribe_response.json()["segments"] == 2

    clip_response = client.post(
        "/api/clip-marks",
        json={
            "video_id": video_id,
            "start_seconds": 0,
            "end_seconds": 7,
            "label": "产品战略",
            "note": "适合 15 秒短切",
            "quote": "This is a useful answer.",
            "status": "ready",
        },
    )
    assert clip_response.status_code == 200

    srt = client.get(f"/api/videos/{video_id}/export?format=srt&language=zh")
    csv = client.get(f"/api/videos/{video_id}/export?format=csv")
    assert srt.status_code == 200
    assert "【中译】" in srt.text
    assert csv.status_code == 200
    assert "产品战略" in csv.text


def test_download_requires_authorization_note() -> None:
    client = make_client()
    client.post("/api/sync/youtube", json={})
    video_id = client.get("/api/videos").json()[0]["id"]
    response = client.post(
        f"/api/videos/{video_id}/download",
        json={"authorization_note": "", "quality": "720p", "include_subtitles": True, "include_thumbnail": True},
    )
    assert response.status_code == 400
