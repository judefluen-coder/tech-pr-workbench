from __future__ import annotations

from pathlib import Path

from app.clip_export import render_clip_marks
from app.db import get_connection, now_iso
from app.jobs import enqueue_job, fail_job, update_job
from app.render_options import normalize_render_options


def create_render_clips_job(video_id: int, options: dict) -> dict:
    with get_connection() as conn:
        video = conn.execute("SELECT id FROM videos WHERE id = ?", (video_id,)).fetchone()
    if not video:
        raise ValueError("视频不存在。")
    render_options = normalize_render_options(options)
    payload = {
        "video_id": video_id,
        "destination": options.get("destination") or "downloads",
        "output_dir": options.get("output_dir") or "",
        "filename": options.get("filename") or "",
        "target_duration_seconds": float(options.get("target_duration_seconds") or 0),
        "clip_status_filter": options.get("clip_status_filter") or "all",
        **render_options,
    }
    return enqueue_job("render_clips", payload, "已加入视频导出队列", dedupe_video_id=video_id)


def run_render_clips_job(job_id: int, payload: dict) -> None:
    video_id = int(payload.get("video_id") or 0)
    try:
        update_job(job_id, "running", "正在检查视频、字幕和剪辑序列", progress=5)
        result = render_clip_marks(
            video_id,
            destination=str(payload.get("destination") or "downloads"),
            destination_dir=str(payload.get("output_dir") or ""),
            filename=str(payload.get("filename") or ""),
            target_duration_seconds=float(payload.get("target_duration_seconds") or 0),
            clip_status_filter=str(payload.get("clip_status_filter") or "all"),
            output_profile=str(payload.get("output_profile") or "source"),
            fit_mode=str(payload.get("fit_mode") or "crop"),
            focus_x=float(payload.get("focus_x") or 0),
            subtitle_style=str(payload.get("subtitle_style") or "standard"),
            subtitle_position=str(payload.get("subtitle_position") or "bottom"),
            logo_asset_id=int(payload["logo_asset_id"]) if payload.get("logo_asset_id") else None,
            logo_position=str(payload.get("logo_position") or "top_right"),
            progress_callback=lambda progress, message: update_job(job_id, "running", message, progress=progress),
        )
        persist_exported_sequence_asset(video_id, result)
        update_job(job_id, "completed", result["message"], progress=100, result=result)
    except Exception as exc:
        fail_job(job_id, str(exc))


def persist_exported_sequence_asset(video_id: int, result: dict) -> None:
    sequence_path = str(result.get("sequence_path") or "")
    if not sequence_path:
        return
    timestamp = now_iso()
    filename = Path(sequence_path).name
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM media_assets
            WHERE video_id = ? AND kind = 'exported_sequence' AND stored_path = ?
            """,
            (video_id, sequence_path),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE media_assets
                SET original_filename = ?, authorization_note = ?, delete_after_processing = 0,
                    processing_status = 'exported', created_at = ?
                WHERE id = ?
                """,
                (filename, "本地剪辑导出的合成序列。", timestamp, existing["id"]),
            )
            return
        conn.execute(
            """
            INSERT INTO media_assets (
              video_id, kind, original_filename, stored_path, transcript_text,
              authorization_note, delete_after_processing, processing_status, created_at
            )
            VALUES (?, 'exported_sequence', ?, ?, '', ?, 0, 'exported', ?)
            """,
            (video_id, filename, sequence_path, "本地剪辑导出的合成序列。", timestamp),
        )
