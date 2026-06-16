from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.db import get_connection, now_iso, row_to_dict


QUALITY_FORMATS = {
    "720p": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/best",
    "1080p": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/best",
    "best": "bv*[ext=mp4]+ba[ext=m4a]/best[ext=mp4]/best",
    "audio": "bestaudio[ext=m4a]/bestaudio/best",
}


def run_authorized_download(video_id: int, authorization_note: str, quality: str = "1080p", include_subtitles: bool = True, include_thumbnail: bool = True) -> dict:
    if not authorization_note.strip():
        raise HTTPException(status_code=400, detail="下载前必须填写授权说明。")
    if settings.download_engine != "yt-dlp":
        raise HTTPException(status_code=400, detail="当前只内置 yt-dlp 下载引擎；xiadown 可作为外部下载器导入目录使用。")

    with get_connection() as conn:
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(status_code=404, detail="视频不存在。")
        timestamp = now_iso()
        cursor = conn.execute(
            """
            INSERT INTO download_tasks (video_id, engine, status, authorization_note, created_at, updated_at)
            VALUES (?, 'yt-dlp', 'running', ?, ?, ?)
            """,
            (video_id, authorization_note, timestamp, timestamp),
        )
        task_id = cursor.lastrowid

    settings.download_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(video["title"])[:80] or f"video-{video_id}"
    output_template = str(settings.download_dir / f"{video_id}-{slug}.%(ext)s")
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--newline",
        "--no-playlist",
        "--merge-output-format",
        "mp4",
        "-f",
        QUALITY_FORMATS.get(quality, QUALITY_FORMATS["1080p"]),
        "-o",
        output_template,
        "--print",
        "after_move:filepath",
    ]
    _add_js_runtime(command)
    if include_thumbnail:
        command.append("--write-thumbnail")
    command.append(video["url"])

    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60 * 60)
        log = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
        output_path = _find_downloaded_media(completed.stdout, settings.download_dir, video_id)
        if not output_path:
            raise RuntimeError("下载结束但未找到媒体文件。")
        subtitle_paths: dict[str, str] = {}
        if include_subtitles:
            subtitle_paths, subtitle_log = _try_download_subtitles(video_id, video["url"], output_template)
            if subtitle_log:
                log = "\n".join(part for part in [log, subtitle_log] if part)
        status = "completed"
        message = "授权下载完成，已作为本地素材入库。"
        if include_subtitles and not subtitle_paths:
            message = "视频已下载；字幕暂未拉取成功，将进入转写或等待手动字幕。"
    except Exception as exc:
        log = getattr(exc, "stderr", "") or str(exc)
        output_path = ""
        subtitle_paths = {}
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
        raise HTTPException(status_code=502, detail=f"下载失败：{message}")
    return {"task": task, "message": message, "subtitles": subtitle_paths}


def list_download_tasks(video_id: int | None = None) -> list[dict]:
    with get_connection() as conn:
        if video_id:
            rows = conn.execute("SELECT * FROM download_tasks WHERE video_id = ? ORDER BY id DESC", (video_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM download_tasks ORDER BY id DESC LIMIT 50").fetchall()
        return [row_to_dict(row) for row in rows]


def _slugify(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value, flags=re.UNICODE)
    return value.strip("-_.")


def _add_js_runtime(command: list[str]) -> None:
    node = shutil.which("node")
    if node:
        command.extend(["--js-runtimes", f"node:{node}"])


def _try_download_subtitles(video_id: int, url: str, output_template: str) -> tuple[dict[str, str], str]:
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--newline",
        "--skip-download",
        "--no-playlist",
        "-o",
        output_template,
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "en.*,zh.*,zh-Hans,zh-Hant",
    ]
    _add_js_runtime(command)
    command.append(url)
    completed = subprocess.run(command, capture_output=True, text=True, timeout=20 * 60)
    log = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    if completed.returncode != 0:
        return find_downloaded_subtitles(video_id), f"字幕下载失败但视频已保留：{log[-3000:]}"
    return find_downloaded_subtitles(video_id), log


def _find_downloaded_media(stdout: str, download_dir: Path, video_id: int) -> str:
    candidates = []
    for line in stdout.splitlines():
        path = Path(line.strip())
        if path.exists() and path.suffix.lower() in {".mp4", ".m4a", ".mp3", ".mov", ".webm", ".mkv"}:
            candidates.append(path)
    if candidates:
        return str(candidates[-1])
    files = sorted(
        [path for path in download_dir.glob(f"{video_id}-*") if path.suffix.lower() in {".mp4", ".m4a", ".mp3", ".mov", ".webm", ".mkv"}],
        key=lambda path: path.stat().st_mtime,
    )
    return str(files[-1]) if files else ""


def find_downloaded_subtitles(video_id: int) -> dict[str, str]:
    subtitle_files = sorted(
        [
            path
            for path in settings.download_dir.glob(f"{video_id}-*")
            if path.suffix.lower() in {".vtt", ".srt"}
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    result: dict[str, str] = {}
    for path in subtitle_files:
        lang = _subtitle_language(path)
        if lang and lang not in result:
            result[lang] = str(path)
    return result


def _subtitle_language(path: Path) -> str:
    stem = path.stem.lower()
    if any(token in stem for token in (".zh", "zh-hans", "zh-hant", "zh_cn", "zh-tw", "chinese")):
        return "zh"
    if any(token in stem for token in (".en", "en-us", "en-gb", "english")):
        return "en"
    return ""
