from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.config import settings
from app.db import get_connection, now_iso, row_to_dict
from app.scoring import people_signals_for_video, priority_score, topic_confidence
from app.summaries import build_discovery_summary, looks_related_to_template
from app.templates import DEFAULT_TEMPLATE_SLUG, get_template_from_conn


BILIBILI_SEARCH_QUERIES = [
    "AI 采访",
    "人工智能 访谈",
    "大模型 访谈",
    "OpenAI 访谈",
    "Anthropic 访谈",
    "DeepSeek 访谈",
]
BILIBILI_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.bilibili.com",
}
MEDIA_SUFFIXES = {".mp4", ".m4a", ".mp3", ".mov", ".webm", ".mkv", ".flv"}
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def sync_bilibili(
    limit_per_query: int = 5,
    published_after: str | None = None,
    published_before: str | None = None,
    template_slug: str = DEFAULT_TEMPLATE_SLUG,
) -> dict:
    if not settings.bilibili_discovery_enabled or not settings.opencli_discovery_enabled:
        return {"mode": "disabled", "queried": 0, "candidates": 0, "inserted": 0, "message": "B站抓取已关闭。"}

    opencli = _opencli_path()
    if not opencli:
        return {"mode": "opencli_bilibili", "queried": 0, "candidates": 0, "inserted": 0, "message": "未找到 opencli，暂不能抓取 B站。"}

    raw_items: list[dict] = []
    errors: list[str] = []
    queried = 0
    channel_limit = settings.bilibili_channel_scan_limit
    with get_connection() as conn:
        template = get_template_from_conn(conn, template_slug)
    for uid in settings.bilibili_channel_uids[:channel_limit]:
        queried += 1
        try:
            raw_items.extend(_run_opencli_user_videos(opencli, uid, max(limit_per_query, 5)))
        except Exception as exc:
            errors.append(f"账号 {uid} 抓取失败：{exc}")

    queries = template.get("bilibili_queries") or BILIBILI_SEARCH_QUERIES
    for query in queries[: max(3, min(len(queries), limit_per_query))]:
        queried += 1
        try:
            raw_items.extend(_run_opencli_search(opencli, query, max(limit_per_query, 5)))
        except Exception as exc:
            errors.append(f"关键词 {query} 抓取失败：{exc}")

    seen: set[str] = set()
    enriched: list[dict] = []
    for item in raw_items:
        bvid = _extract_bvid(str(item.get("url") or item.get("bvid") or ""))
        if not bvid or bvid in seen:
            continue
        seen.add(bvid)
        metadata = _fetch_bilibili_view(bvid) or _metadata_from_opencli_item(bvid, item)
        if metadata:
            enriched.append(metadata)

    inserted = _upsert_bilibili_items(enriched, published_after, published_before, template["slug"])
    message = "已同步 B站候选，并按真实发布时间过滤。"
    if errors:
        message += f" 部分来源失败 {len(errors)} 个。"
    return {
        "mode": "opencli_bilibili",
        "queried": queried,
        "candidates": len(enriched),
        "inserted": inserted,
        "errors": errors[:6],
        "message": message,
    }


def fetch_bilibili_subtitle_segments(bvid: str) -> list[dict]:
    opencli = _require_opencli()
    completed = subprocess.run(
        [opencli, "bilibili", "subtitle", bvid, "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    payload = _json_from_opencli(completed.stdout)
    if not isinstance(payload, list):
        return []
    segments = []
    for row in payload:
        text = str(row.get("content") or "").strip()
        if not text:
            continue
        segments.append(
            {
                "start_seconds": _seconds_from_bilibili_time(row.get("from")),
                "end_seconds": _seconds_from_bilibili_time(row.get("to")),
                "text": text,
            }
        )
    return [segment for segment in segments if segment["end_seconds"] > segment["start_seconds"]]


def download_bilibili_authorized(video_id: int, bvid: str, authorization_note: str, quality: str = "1080p") -> dict:
    if not authorization_note.strip():
        raise RuntimeError("下载前必须填写授权说明。")
    opencli = _require_opencli()
    timestamp = now_iso()
    with get_connection() as conn:
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise RuntimeError("视频不存在。")
        cursor = conn.execute(
            """
            INSERT INTO download_tasks (video_id, engine, status, authorization_note, created_at, updated_at)
            VALUES (?, 'opencli-bilibili', 'running', ?, ?, ?)
            """,
            (video_id, authorization_note, timestamp, timestamp),
        )
        task_id = cursor.lastrowid

    output_dir = settings.download_dir / f"bilibili-{video_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        opencli,
        "bilibili",
        "download",
        bvid,
        "--output",
        str(output_dir),
        "--quality",
        _bilibili_quality(quality),
        "--format",
        "json",
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60 * 60)
        log = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
        output_path = _find_downloaded_media(output_dir)
        if not output_path:
            raise RuntimeError("下载结束但未找到媒体文件。")
        status = "completed"
        message = "B站视频已下载为本地素材。"
    except Exception as exc:
        log = getattr(exc, "stderr", "") or str(exc)
        output_path = ""
        status = "failed"
        message = str(exc)

    with get_connection() as conn:
        conn.execute(
            "UPDATE download_tasks SET status = ?, output_path = ?, log = ?, updated_at = ? WHERE id = ?",
            (status, str(output_path), log[-8000:], now_iso(), task_id),
        )
        if status == "completed":
            conn.execute(
                """
                INSERT INTO media_assets (
                  video_id, kind, original_filename, stored_path, transcript_text,
                  authorization_note, delete_after_processing, processing_status, created_at
                )
                VALUES (?, 'media', ?, ?, '', ?, 0, 'imported', ?)
                """,
                (video_id, Path(output_path).name, str(output_path), authorization_note, now_iso()),
            )
            conn.execute("UPDATE videos SET status = 'imported', updated_at = ? WHERE id = ?", (now_iso(), video_id))
        task = row_to_dict(conn.execute("SELECT * FROM download_tasks WHERE id = ?", (task_id,)).fetchone())
    if status == "failed":
        raise RuntimeError(f"B站下载失败：{message}")
    return {"task": task, "message": message, "media_path": str(output_path)}


def _run_opencli_search(opencli: str, query: str, limit: int) -> list[dict]:
    completed = subprocess.run(
        [opencli, "bilibili", "search", query, "--type", "video", "--limit", str(min(limit, 12)), "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    payload = _json_from_opencli(completed.stdout)
    return payload if isinstance(payload, list) else []


def _run_opencli_user_videos(opencli: str, uid: str, limit: int) -> list[dict]:
    completed = subprocess.run(
        [opencli, "bilibili", "user-videos", uid, "--limit", str(min(limit, 12)), "--order", "pubdate", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    payload = _json_from_opencli(completed.stdout)
    return payload if isinstance(payload, list) else []


def _fetch_bilibili_view(bvid: str) -> dict | None:
    try:
        response = httpx.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
            headers=BILIBILI_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    if payload.get("code") != 0:
        return None
    data = payload.get("data") or {}
    owner = data.get("owner") or {}
    stat = data.get("stat") or {}
    pubdate = int(data.get("pubdate") or 0)
    published_at = datetime.fromtimestamp(pubdate, tz=timezone.utc).replace(microsecond=0).isoformat() if pubdate else ""
    return {
        "external_id": data.get("bvid") or bvid,
        "url": f"https://www.bilibili.com/video/{data.get('bvid') or bvid}",
        "title": data.get("title") or "",
        "description": data.get("desc") or "",
        "channel_title": owner.get("name") or "",
        "published_at": published_at,
        "duration_seconds": int(data.get("duration") or 0),
        "view_count": int(stat.get("view") or 0),
        "like_count": int(stat.get("like") or 0),
        "thumbnail_url": data.get("pic") or "",
    }


def _metadata_from_opencli_item(bvid: str, item: dict) -> dict | None:
    published_at = _published_from_local_date(str(item.get("date") or ""))
    if not published_at:
        return None
    return {
        "external_id": bvid,
        "url": f"https://www.bilibili.com/video/{bvid}",
        "title": item.get("title") or "",
        "description": "",
        "channel_title": item.get("author") or "",
        "published_at": published_at,
        "duration_seconds": 0,
        "view_count": int(item.get("plays") or 0),
        "like_count": int(item.get("likes") or 0),
        "thumbnail_url": "",
    }


def _upsert_bilibili_items(
    items: list[dict],
    published_after: str | None,
    published_before: str | None,
    template_slug: str = DEFAULT_TEMPLATE_SLUG,
) -> int:
    if not items:
        return 0
    with get_connection() as conn:
        template = get_template_from_conn(conn, template_slug)
        people = [dict(row) for row in conn.execute("SELECT * FROM people WHERE template_slug = ?", (template["slug"],)).fetchall()]
        inserted_or_updated = 0
        for item in items:
            title = item.get("title", "")
            description = item.get("description", "") or ""
            channel = item.get("channel_title") or ""
            if not looks_related_to_template(title, description, channel, template):
                continue
            published_at = item.get("published_at", "")
            if not published_at or not _within_utc_window(published_at, published_after, published_before):
                continue
            matches, names, candidate_people, reason = people_signals_for_video(title, description, channel, people)
            confidence = topic_confidence(title, description, int(item.get("duration_seconds") or 0), template.get("scoring_terms") or None)
            view_count = int(item.get("view_count") or 0)
            score = priority_score(matches, confidence, published_at, channel, view_count)
            summary = build_discovery_summary(title, description, channel, names or candidate_people, template)
            timestamp = now_iso()
            cursor = conn.execute(
                """
                INSERT INTO videos (
                  template_slug, platform, external_id, url, title, description, channel_title, published_at,
                  duration_seconds, view_count, like_count, thumbnail_url, matched_people,
                  candidate_people, people_match_reason, interview_confidence, priority_score, status, compliance_note, summary, source_tier, created_at, updated_at
                )
                VALUES (?, 'bilibili', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', 'metadata_only', ?, 'stable', ?, ?)
                ON CONFLICT(platform, external_id) DO UPDATE SET
                  template_slug = excluded.template_slug,
                  url = excluded.url,
                  title = excluded.title,
                  description = excluded.description,
                  channel_title = excluded.channel_title,
                  published_at = excluded.published_at,
                  duration_seconds = excluded.duration_seconds,
                  view_count = excluded.view_count,
                  like_count = excluded.like_count,
                  thumbnail_url = excluded.thumbnail_url,
                  matched_people = excluded.matched_people,
                  candidate_people = excluded.candidate_people,
                  people_match_reason = excluded.people_match_reason,
                  interview_confidence = excluded.interview_confidence,
                  priority_score = excluded.priority_score,
                  summary = excluded.summary,
                  source_tier = excluded.source_tier,
                  updated_at = excluded.updated_at
                """,
                (
                    template["slug"],
                    str(item["external_id"]),
                    item["url"],
                    title,
                    description,
                    channel,
                    published_at,
                    int(item.get("duration_seconds") or 0),
                    view_count,
                    int(item.get("like_count") or 0),
                    item.get("thumbnail_url") or "",
                    names,
                    candidate_people,
                    reason,
                    confidence,
                    score,
                    summary,
                    timestamp,
                    timestamp,
                ),
            )
            video_row = conn.execute("SELECT id FROM videos WHERE platform = 'bilibili' AND external_id = ?", (str(item["external_id"]),)).fetchone()
            if video_row:
                conn.execute(
                    "INSERT OR IGNORE INTO video_template_links (video_id, template_slug, created_at) VALUES (?, ?, ?)",
                    (video_row["id"], template["slug"], now_iso()),
                )
            inserted_or_updated += max(cursor.rowcount, 0)
        return inserted_or_updated


def _json_from_opencli(output: str) -> object:
    text = _strip_opencli_update_notice(output)
    return json.loads(text) if text else []


def _strip_opencli_update_notice(output: str) -> str:
    text = output.strip()
    if "\n\n  Update available:" in text:
        text = text.split("\n\n  Update available:", 1)[0].strip()
    return text


def _extract_bvid(value: str) -> str:
    match = re.search(r"(BV[0-9A-Za-z]+)", value)
    return match.group(1) if match else ""


def _published_from_local_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return ""
    local = datetime.combine(parsed, time.min, tzinfo=BEIJING_TZ)
    return local.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _within_utc_window(published_at: str, published_after: str | None, published_before: str | None) -> bool:
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    if published_after:
        start = datetime.fromisoformat(published_after.replace("Z", "+00:00"))
        if published < start:
            return False
    if published_before:
        end = datetime.fromisoformat(published_before.replace("Z", "+00:00"))
        if published >= end:
            return False
    return True


def _seconds_from_bilibili_time(value: object) -> float:
    text = str(value or "").strip().removesuffix("s")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _opencli_path() -> str:
    return shutil.which(settings.opencli_path) or shutil.which("opencli") or ""


def _require_opencli() -> str:
    opencli = _opencli_path()
    if not opencli:
        raise RuntimeError("未找到 opencli，无法处理 B站视频。")
    return opencli


def _bilibili_quality(quality: str) -> str:
    if quality in {"best", "1080p", "720p", "480p"}:
        return quality
    return "1080p"


def _find_downloaded_media(output_dir: Path) -> str:
    files = sorted(
        [path for path in output_dir.rglob("*") if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES],
        key=lambda path: path.stat().st_mtime,
    )
    return str(files[-1]) if files else ""
