from __future__ import annotations

from app.ai import transcribe_and_translate
from app.db import get_connection, now_iso, row_to_dict
from app.downloads import run_authorized_download
from app.schemas import AutomationRequest
from app.youtube import sync_youtube


async def run_automation(payload: AutomationRequest) -> dict:
    sync_result = await sync_youtube(payload.days_back, payload.limit_per_query, include_demo_when_unconfigured=True)
    actions: list[dict] = [{"step": "discover", "status": "completed", "message": sync_result.get("message", "")}]

    with get_connection() as conn:
        candidates = [
            row_to_dict(row)
            for row in conn.execute(
                """
                SELECT * FROM videos
                WHERE status IN ('new', 'shortlisted')
                ORDER BY priority_score DESC, published_at DESC, id DESC
                LIMIT 5
                """
            ).fetchall()
        ]
        for candidate in candidates:
            if candidate["priority_score"] >= payload.shortlist_threshold and candidate["status"] == "new":
                conn.execute("UPDATE videos SET status = 'shortlisted', updated_at = ? WHERE id = ?", (now_iso(), candidate["id"]))
                actions.append({"step": "shortlist", "status": "completed", "video_id": candidate["id"], "message": candidate["title"]})

    if payload.auto_download:
        if not payload.authorization_note.strip():
            actions.append({"step": "download", "status": "skipped", "message": "未填写授权说明，已跳过自动下载。"})
        else:
            for candidate in candidates[:2]:
                try:
                    result = run_authorized_download(
                        video_id=candidate["id"],
                        authorization_note=payload.authorization_note,
                        quality="1080p",
                        include_subtitles=True,
                        include_thumbnail=True,
                    )
                    actions.append({"step": "download", "status": "completed", "video_id": candidate["id"], "message": result["message"]})
                except Exception as exc:
                    actions.append({"step": "download", "status": "failed", "video_id": candidate["id"], "message": str(exc)})

    if payload.auto_transcribe:
        with get_connection() as conn:
            imported = [
                row_to_dict(row)
                for row in conn.execute(
                    "SELECT * FROM videos WHERE status = 'imported' ORDER BY priority_score DESC LIMIT 3"
                ).fetchall()
            ]
        for item in imported:
            try:
                result = transcribe_and_translate(item["id"])
                actions.append({"step": "transcribe", "status": "completed", "video_id": item["id"], "message": result["message"]})
            except Exception as exc:
                actions.append({"step": "transcribe", "status": "failed", "video_id": item["id"], "message": str(exc)})

    return {"ok": True, "actions": actions}

