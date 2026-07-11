from __future__ import annotations

import json
import re
from pathlib import Path

from app.ai import normalize_transcript_segments, parse_transcript_text, save_transcript_segments, transcribe_and_translate, translate_segments_to_zh
from app.bilibili import download_bilibili_authorized, fetch_bilibili_subtitle_segments
from app.config import settings
from app.db import get_connection, now_iso, row_to_dict
from app.downloads import find_downloaded_subtitles, run_authorized_download
from app.scoring import people_signals_for_video, priority_score
from app.summaries import build_transcript_summary

CLIP_MARK_ORDER_SQL = "position IS NULL, position, start_seconds, id"


def create_download_translate_job(video_id: int, authorization_note: str = "", quality: str = "1080p") -> dict:
    timestamp = now_iso()
    with get_connection() as conn:
        video = conn.execute("SELECT id, title FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise ValueError("视频不存在。")
        cursor = conn.execute(
            """
            INSERT INTO jobs (type, status, message, payload, created_at, updated_at)
            VALUES ('download_translate', 'queued', '已加入下载翻译队列', ?, ?, ?)
            """,
            (
                json.dumps({"video_id": video_id, "quality": quality}, ensure_ascii=False),
                timestamp,
                timestamp,
            ),
        )
        job_id = cursor.lastrowid
    return {"job_id": job_id, "video_id": video_id, "message": "已开始下载并翻译，请稍等。"}


def run_download_translate_job(job_id: int, video_id: int, authorization_note: str = "", quality: str = "1080p") -> None:
    note = authorization_note.strip() or "用户点击下载并翻译，用于本地剪辑工作台处理。"
    try:
        video = _get_video(video_id)
        if _is_demo_video(video):
            _update_job(job_id, "running", "这是演示候选，正在生成可试用字幕", video_id, "translating")
            en_segments = _demo_segments(video)
            zh_segments = translate_segments_to_zh(en_segments)
            save_transcript_segments(video_id, en_segments, zh_segments, "demo_transcript", "demo_translation", "clip_ready")
            _finish_translated_video(video_id, zh_segments)
            _update_job(job_id, "completed", "演示字幕已生成；真实下载需要有效原始视频链接", video_id, "clip_ready")
            return

        if video.get("platform") == "bilibili":
            _run_bilibili_download_translate(job_id, video, note, quality)
            return

        _update_job(job_id, "running", "正在下载原始视频和可用字幕", video_id, "downloading")
        download = run_authorized_download(
            video_id=video_id,
            authorization_note=note,
            quality=quality,
            include_subtitles=True,
            include_thumbnail=True,
        )

        subtitles = download.get("subtitles", {})
        if subtitles.get("zh"):
            _update_job(job_id, "running", "检测到中文字幕，正在直接导入", video_id, "subtitle_fetching")
            zh_segments = _segments_from_subtitle(subtitles["zh"])
            en_segments = _segments_from_subtitle(subtitles.get("en", "")) if subtitles.get("en") else []
            save_transcript_segments(video_id, en_segments, zh_segments, "downloaded_subtitle", "downloaded_zh_subtitle", "clip_ready")
            _finish_translated_video(video_id, zh_segments)
            _update_job(job_id, "completed", "已导入原中文字幕，可进入剪辑工作台", video_id, "clip_ready")
            return

        if subtitles.get("en"):
            _update_job(job_id, "running", "检测到英文字幕，正在本地翻译为中文", video_id, "translating")
            en_segments = _segments_from_subtitle(subtitles["en"])
            zh_segments = translate_segments_to_zh(en_segments)
            save_transcript_segments(video_id, en_segments, zh_segments, "downloaded_en_subtitle", "local_translation", "clip_ready")
            _finish_translated_video(video_id, zh_segments)
            _update_job(job_id, "completed", "英文字幕已翻译为中文，可进入剪辑工作台", video_id, "clip_ready")
            return

        if not settings.local_asr_enabled and not (settings.cloud_ai_enabled and settings.openai_api_key):
            _update_job(
                job_id,
                "completed",
                "视频已下载，但没有检测到可用字幕；请启用本地转写或手动导入字幕后再生成中文字幕。",
                video_id,
                "imported",
            )
            return

        _update_job(job_id, "running", "没有可用字幕，正在转写音频并翻译", video_id, "transcribing")
        result = transcribe_and_translate(video_id)
        if not result.get("ok"):
            raise RuntimeError(result.get("message", "转写翻译失败"))
        _promote_translated_to_clip_ready(video_id)
        _update_job(job_id, "completed", "已完成转写和中文字幕，可进入剪辑工作台", video_id, "clip_ready")
    except Exception as exc:
        _mark_failed(job_id, video_id, str(exc))


def create_subtitle_reprocess_job(video_id: int) -> dict:
    timestamp = now_iso()
    with get_connection() as conn:
        video = conn.execute("SELECT id FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise ValueError("视频不存在。")
        cursor = conn.execute(
            """
            INSERT INTO jobs (type, status, message, payload, created_at, updated_at)
            VALUES ('subtitle_reprocess', 'queued', '已加入字幕重处理队列', ?, ?, ?)
            """,
            (json.dumps({"video_id": video_id}, ensure_ascii=False), timestamp, timestamp),
        )
        job_id = cursor.lastrowid
    return {"job_id": job_id, "video_id": video_id, "message": "已开始重新处理字幕。"}


def run_subtitle_reprocess_job(job_id: int, video_id: int) -> None:
    try:
        video = _get_video(video_id)
        _update_job(job_id, "running", "正在读取已有字幕并清理重复片段", video_id)
        subtitles = find_downloaded_subtitles(video_id)

        if subtitles.get("zh"):
            zh_segments = _segments_from_subtitle(subtitles["zh"])
            en_segments = _segments_from_subtitle(subtitles["en"]) if subtitles.get("en") else []
            en_source = "reprocessed_downloaded_subtitle"
            zh_source = "reprocessed_downloaded_zh_subtitle"
        elif subtitles.get("en"):
            en_segments = _segments_from_subtitle(subtitles["en"])
            _update_job(job_id, "running", "字幕已清理，正在重新生成中文翻译", video_id)
            zh_segments = translate_segments_to_zh(en_segments)
            en_source = "reprocessed_downloaded_en_subtitle"
            zh_source = "reprocessed_local_translation"
        else:
            en_segments, zh_segments = _stored_transcript_segments(video_id)
            if en_segments:
                _update_job(job_id, "running", "没有找到原字幕文件，正在根据已有英文字幕重新翻译", video_id)
                zh_segments = translate_segments_to_zh(en_segments)
                en_source = "reprocessed_stored_transcript"
                zh_source = "reprocessed_local_translation"
            elif zh_segments:
                en_source = "none"
                zh_source = "reprocessed_stored_subtitle"
            else:
                raise RuntimeError("没有可重新处理的字幕，请先下载视频或导入字幕。")

        final_status = _status_after_subtitle_reprocess(video_id, video.get("status", ""))
        save_transcript_segments(video_id, en_segments, zh_segments, en_source, zh_source, final_status)
        _finish_translated_video(video_id, zh_segments, final_status)
        _update_job(job_id, "completed", f"字幕已重新处理：{len(zh_segments)} 条中文，{len(en_segments)} 条英文", video_id)
    except Exception as exc:
        _mark_reprocess_failed(job_id, video_id, str(exc))


def get_job(job_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise ValueError("任务不存在。")
        return row_to_dict(row)


def clip_payload(video_id: int) -> dict:
    with get_connection() as conn:
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise ValueError("视频不存在。")
        transcripts = [
            row_to_dict(row)
            for row in conn.execute("SELECT * FROM transcripts WHERE video_id = ? ORDER BY language, start_seconds", (video_id,)).fetchall()
        ]
        clips = [
            row_to_dict(row)
            for row in conn.execute(f"SELECT * FROM clip_marks WHERE video_id = ? ORDER BY {CLIP_MARK_ORDER_SQL}", (video_id,)).fetchall()
        ]
        assets = [
            media_asset_with_url(row_to_dict(row))
            for row in conn.execute("SELECT * FROM media_assets WHERE video_id = ? ORDER BY id DESC", (video_id,)).fetchall()
        ]
    media_asset = next((asset for asset in assets if asset["kind"] == "media" and asset.get("stored_path")), None)
    return {
        "video": row_to_dict(video),
        "transcripts": transcripts,
        "clip_marks": clips,
        "media_assets": assets,
        "media_url": media_asset.get("url", "") if media_asset else "",
    }


def _segments_from_subtitle(path: str) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    segments = parse_transcript_text(text)
    if not segments:
        raise RuntimeError(f"字幕文件无法解析：{Path(path).name}")
    return segments


def _stored_transcript_segments(video_id: int) -> tuple[list[dict], list[dict]]:
    with get_connection() as conn:
        rows = [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT language, start_seconds, end_seconds, text FROM transcripts WHERE video_id = ? ORDER BY language, start_seconds",
                (video_id,),
            ).fetchall()
        ]
    en_segments = normalize_transcript_segments([row for row in rows if row["language"] == "en"])
    zh_segments = normalize_transcript_segments([row for row in rows if row["language"] == "zh"])
    return en_segments, zh_segments


def _get_video(video_id: int) -> dict:
    with get_connection() as conn:
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise RuntimeError("视频不存在。")
        return row_to_dict(video)


def _is_demo_video(video: dict) -> bool:
    return str(video.get("external_id", "")).startswith("demo-") or "youtube.com/results" in str(video.get("url", ""))


def _run_bilibili_download_translate(job_id: int, video: dict, note: str, quality: str) -> None:
    video_id = int(video["id"])
    bvid = _bvid_from_video(video)
    if not bvid:
        raise RuntimeError("B站视频缺少 BV 号，无法处理。")

    subtitle_error = ""
    _update_job(job_id, "running", "正在拉取 B站中文字幕", video_id, "subtitle_fetching")
    try:
        zh_segments = fetch_bilibili_subtitle_segments(bvid)
    except Exception as exc:
        zh_segments = []
        subtitle_error = str(exc)

    if zh_segments:
        _update_job(job_id, "running", "已拉取 B站中文字幕，正在下载原始视频", video_id, "downloading")
        download_bilibili_authorized(video_id, bvid, note, quality)
        save_transcript_segments(video_id, [], zh_segments, "none", "bilibili_subtitle", "clip_ready")
        _finish_translated_video(video_id, zh_segments)
        _update_job(job_id, "completed", "已下载 B站视频并拉取中文字幕，可进入剪辑工作台", video_id, "clip_ready")
        return

    _update_job(job_id, "running", "没有检测到 B站字幕，正在下载原始视频", video_id, "downloading")
    download_bilibili_authorized(video_id, bvid, note, quality)

    if not settings.local_asr_enabled and not (settings.cloud_ai_enabled and settings.openai_api_key):
        hint = f"字幕拉取失败：{subtitle_error}。" if subtitle_error else ""
        raise RuntimeError(f"{hint}视频已尝试下载，但没有可用字幕且未开启本地转写。请开启 LOCAL_ASR_ENABLED 或手动导入字幕。")

    _update_job(job_id, "running", "已下载 B站视频，正在转写并生成中文字幕", video_id, "transcribing")
    result = transcribe_and_translate(video_id)
    if not result.get("ok"):
        raise RuntimeError(result.get("message", "转写翻译失败"))
    _promote_translated_to_clip_ready(video_id)
    _update_job(job_id, "completed", "B站视频已完成转写和中文字幕，可进入剪辑工作台", video_id, "clip_ready")


def _bvid_from_video(video: dict) -> str:
    for value in (video.get("external_id", ""), video.get("url", "")):
        match = re.search(r"(BV[0-9A-Za-z]+)", str(value))
        if match:
            return match.group(1)
    return ""


def _demo_segments(video: dict) -> list[dict]:
    title = video.get("title", "AI interview")
    return [
        {"start_seconds": 0, "end_seconds": 7, "text": f"This interview opens with the main AI theme: {title}."},
        {"start_seconds": 7, "end_seconds": 16, "text": "The guest connects product strategy, model capability, and market timing."},
        {"start_seconds": 16, "end_seconds": 27, "text": "This is a useful section for PR review before creating a short clip."},
    ]


def _finish_translated_video(video_id: int, zh_segments: list[dict], status: str = "clip_ready") -> None:
    summary = build_transcript_summary(zh_segments)
    matched_names, candidate_people, reason, score = _people_signals_after_transcript(video_id)
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE videos
            SET status = ?, summary = ?, matched_people = ?, candidate_people = ?,
                people_match_reason = ?, priority_score = ?, last_error = '', updated_at = ?
            WHERE id = ?
            """,
            (status, summary, matched_names, candidate_people, reason, score, now_iso(), video_id),
        )


def _status_after_subtitle_reprocess(video_id: int, current_status: str) -> str:
    if current_status == "exported":
        return "exported"
    with get_connection() as conn:
        has_clips = conn.execute("SELECT 1 FROM clip_marks WHERE video_id = ? LIMIT 1", (video_id,)).fetchone()
    return "clipped" if has_clips else "clip_ready"


def _promote_translated_to_clip_ready(video_id: int) -> None:
    with get_connection() as conn:
        zh_segments = [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT * FROM transcripts WHERE video_id = ? AND language = 'zh' ORDER BY start_seconds",
                (video_id,),
            ).fetchall()
        ]
    _finish_translated_video(video_id, zh_segments)


def _people_signals_after_transcript(video_id: int) -> tuple[str, str, str, float]:
    with get_connection() as conn:
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        people = [dict(row) for row in conn.execute("SELECT * FROM people").fetchall()]
        transcripts = [
            row_to_dict(row)
            for row in conn.execute(
                "SELECT text FROM transcripts WHERE video_id = ? ORDER BY language, start_seconds LIMIT 80",
                (video_id,),
            ).fetchall()
        ]
    if not video:
        return "", "", "视频不存在，无法识别人物", 0
    video_dict = row_to_dict(video)
    transcript_text = " ".join(row.get("text", "") for row in transcripts)
    matches, matched_names, candidate_people, reason = people_signals_for_video(
        video_dict.get("title", ""),
        video_dict.get("description", ""),
        video_dict.get("channel_title", ""),
        people,
        transcript_text,
    )
    score = priority_score(
        matches,
        float(video_dict.get("interview_confidence") or 0),
        video_dict.get("published_at", ""),
        video_dict.get("channel_title", ""),
        int(video_dict.get("view_count") or 0),
    )
    return matched_names, candidate_people, reason, score


def _update_job(job_id: int, status: str, message: str, video_id: int, video_status: str | None = None) -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, message = ?, updated_at = ? WHERE id = ?",
            (status, message, timestamp, job_id),
        )
        if video_status:
            conn.execute(
                "UPDATE videos SET status = ?, last_error = '', updated_at = ? WHERE id = ?",
                (video_status, timestamp, video_id),
            )


def _mark_failed(job_id: int, video_id: int, message: str) -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'failed', message = ?, updated_at = ? WHERE id = ?",
            (message, timestamp, job_id),
        )
        conn.execute(
            "UPDATE videos SET status = 'failed', last_error = ?, updated_at = ? WHERE id = ?",
            (message, timestamp, video_id),
        )


def _mark_reprocess_failed(job_id: int, video_id: int, message: str) -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'failed', message = ?, updated_at = ? WHERE id = ?",
            (message, timestamp, job_id),
        )
        conn.execute(
            "UPDATE videos SET last_error = ?, updated_at = ? WHERE id = ?",
            (message, timestamp, video_id),
        )


def media_asset_with_url(asset: dict) -> dict:
    return {**asset, "url": _media_url(asset.get("stored_path", ""))}


def _media_url(path: str) -> str:
    media_path = Path(path)
    try:
        relative = media_path.relative_to(settings.download_dir)
        return f"/media/downloads/{relative.as_posix()}"
    except ValueError:
        pass
    try:
        relative = media_path.relative_to(settings.upload_dir)
        return f"/media/uploads/{relative.as_posix()}"
    except ValueError:
        pass
    try:
        relative = media_path.relative_to(settings.export_dir)
        return f"/media/exports/{relative.as_posix()}"
    except ValueError:
        return ""
