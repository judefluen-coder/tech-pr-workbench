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


def test_templates_can_be_listed_cloned_and_updated() -> None:
    client = make_client()
    templates = client.get("/api/templates")
    assert templates.status_code == 200
    slugs = {item["slug"] for item in templates.json()}
    assert {"ai-interviews", "tech-executive-interviews", "competitor-launches"}.issubset(slugs)

    clone = client.post("/api/templates/competitor-launches/clone", json={"name": "新能源发布监测"})
    assert clone.status_code == 200
    cloned = clone.json()
    assert cloned["is_builtin"] == 0
    assert cloned["base_slug"] == "competitor-launches"

    update = client.patch(
        f"/api/templates/{cloned['slug']}",
        json={
            "description": "追踪新能源产品发布和高管演示。",
            "youtube_queries": ["EV product launch", "battery demo"],
            "topic_terms": ["ev", "battery", "新能源"],
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["description"] == "追踪新能源产品发布和高管演示。"
    assert updated["youtube_queries"] == ["EV product launch", "battery demo"]


def test_daily_report_is_filtered_by_template_slug() -> None:
    client = make_client()
    from app.db import get_connection, now_iso

    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO videos (
              template_slug, platform, external_id, url, title, published_at,
              duration_seconds, status, compliance_note, source_tier, created_at, updated_at
            )
            VALUES (?, 'youtube', ?, ?, ?, '2026-06-14T16:30:00+00:00', 1200, 'ready', 'metadata_only', 'stable', ?, ?)
            """,
            ("ai-interviews", "template-ai-video", "https://www.youtube.com/watch?v=template-ai-video", "AI interview candidate", timestamp, timestamp),
        )
        ai_id = conn.execute("SELECT id FROM videos WHERE external_id = 'template-ai-video'").fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO video_template_links (video_id, template_slug, created_at) VALUES (?, ?, ?)",
            (ai_id, "ai-interviews", timestamp),
        )
        conn.execute(
            """
            INSERT INTO videos (
              template_slug, platform, external_id, url, title, published_at,
              duration_seconds, status, compliance_note, source_tier, created_at, updated_at
            )
            VALUES (?, 'youtube', ?, ?, ?, '2026-06-14T16:35:00+00:00', 900, 'ready', 'metadata_only', 'stable', ?, ?)
            """,
            (
                "competitor-launches",
                "template-launch-video",
                "https://www.youtube.com/watch?v=template-launch-video",
                "Product launch demo candidate",
                timestamp,
                timestamp,
            ),
        )
        launch_id = conn.execute("SELECT id FROM videos WHERE external_id = 'template-launch-video'").fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO video_template_links (video_id, template_slug, created_at) VALUES (?, ?, ?)",
            (launch_id, "competitor-launches", timestamp),
        )

    ai_report = client.get("/api/daily?start_date=2026-06-15&end_date=2026-06-15&template_slug=ai-interviews").json()
    launch_report = client.get("/api/daily?start_date=2026-06-15&end_date=2026-06-15&template_slug=competitor-launches").json()
    assert [item["external_id"] for item in ai_report["items"]] == ["template-ai-video"]
    assert [item["external_id"] for item in launch_report["items"]] == ["template-launch-video"]


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
