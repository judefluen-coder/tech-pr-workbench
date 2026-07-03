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

SINGLE_FILE_FORMATS = {
    "720p": "b[height<=720][ext=mp4]/b[height<=720]/best[height<=720]/best",
    "1080p": "b[height<=1080][ext=mp4]/b[height<=1080]/best[height<=1080]/best",
    "best": "b[ext=mp4]/best",
    "audio": "bestaudio[ext=m4a]/bestaudio/best",
}

MEDIA_SUFFIXES = {".mp4", ".m4a", ".mp3", ".mov", ".webm", ".mkv"}


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
    ffmpeg_path = shutil.which("ffmpeg")
    command = _download_command(output_template, video["url"], quality, bool(ffmpeg_path))

    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60 * 60)
        log = _join_logs(_ffmpeg_fallback_log(quality, ffmpeg_path), _completed_log(completed))
        output_path = _find_downloaded_media(completed.stdout, settings.download_dir, video_id)
        if not output_path:
            raise RuntimeError("下载结束但未找到媒体文件。")
        warnings = []
    except Exception as exc:
        log = _join_logs(_ffmpeg_fallback_log(quality, ffmpeg_path), _exception_log(exc))
        output_path = _find_downloaded_media(_exception_stdout(exc), settings.download_dir, video_id)
        warnings = ["下载工具返回警告，已保留日志"] if output_path else []

    subtitle_paths: dict[str, str] = {}
    if output_path:
        if include_thumbnail:
            try:
                thumbnail_log = _try_download_thumbnail(video["url"], output_template)
            except Exception as exc:
                thumbnail_log = f"封面下载失败但视频已保留：{_exception_log(exc)[-3000:]}"
            if thumbnail_log:
                log = _join_logs(log, thumbnail_log)
            if thumbnail_log.startswith("封面下载失败"):
                warnings.append("封面暂未拉取成功")
        subtitle_paths: dict[str, str] = {}
        if include_subtitles:
            try:
                subtitle_paths, subtitle_log = _try_download_subtitles(video_id, video["url"], output_template)
            except Exception as exc:
                subtitle_paths = {}
                subtitle_log = f"字幕下载失败但视频已保留：{_exception_log(exc)[-3000:]}"
            if subtitle_log:
                log = "\n".join(part for part in [log, subtitle_log] if part)
            if not subtitle_paths:
                warnings.append("字幕暂未拉取成功，将进入转写或等待手动字幕")
        status = "completed"
        message = _success_message(warnings)
    else:
        output_path = ""
        status = "failed"
        message = log[-1200:] or "下载结束但未找到媒体文件。"

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


def _ytdlp_command() -> list[str]:
    configured = settings.ytdlp_path.strip()
    if configured:
        resolved = shutil.which(configured)
        if resolved:
            return [resolved]
        return [configured]
    return [sys.executable, "-m", "yt_dlp"]


def _download_command(output_template: str, url: str, quality: str, ffmpeg_available: bool) -> list[str]:
    command = [
        *_ytdlp_command(),
        "--newline",
        "--no-playlist",
    ]
    if ffmpeg_available:
        command.extend(["--merge-output-format", "mp4"])
    command.extend(
        [
            "-f",
            _quality_format(quality, ffmpeg_available),
            "-o",
            output_template,
            "--print",
            "after_move:filepath",
        ]
    )
    _add_js_runtime(command)
    command.append(url)
    return command


def _quality_format(quality: str, ffmpeg_available: bool) -> str:
    formats = QUALITY_FORMATS if ffmpeg_available else SINGLE_FILE_FORMATS
    return formats.get(quality, formats["1080p"])


def _try_download_thumbnail(url: str, output_template: str) -> str:
    command = [
        *_ytdlp_command(),
        "--newline",
        "--skip-download",
        "--no-playlist",
        "-o",
        output_template,
        "--write-thumbnail",
    ]
    _add_js_runtime(command)
    command.append(url)
    completed = subprocess.run(command, capture_output=True, text=True, timeout=10 * 60)
    log = _completed_log(completed)
    if completed.returncode != 0:
        return f"封面下载失败但视频已保留：{log[-3000:]}"
    return log


def _try_download_subtitles(video_id: int, url: str, output_template: str) -> tuple[dict[str, str], str]:
    command = [
        *_ytdlp_command(),
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
        if _is_media_candidate(path):
            candidates.append(path)
    if candidates:
        return str(candidates[-1])
    files = sorted(
        [path for path in download_dir.glob(f"{video_id}-*") if _is_media_candidate(path)],
        key=lambda path: path.stat().st_mtime,
    )
    return str(files[-1]) if files else ""


def _is_media_candidate(path: Path) -> bool:
    name = path.name.lower()
    return path.exists() and path.suffix.lower() in MEDIA_SUFFIXES and ".temp." not in name and not name.endswith(".part")


def _completed_log(completed: subprocess.CompletedProcess) -> str:
    return _join_logs(completed.stdout or "", completed.stderr or "")


def _exception_log(exc: Exception) -> str:
    stdout = getattr(exc, "stdout", "") or getattr(exc, "output", "")
    stderr = getattr(exc, "stderr", "")
    return _join_logs(stdout or "", stderr or "", str(exc))


def _exception_stdout(exc: Exception) -> str:
    return str(getattr(exc, "stdout", "") or getattr(exc, "output", "") or "")


def _ffmpeg_fallback_log(quality: str, ffmpeg_path: str | None) -> str:
    if ffmpeg_path or quality == "audio":
        return ""
    return "FFmpeg 未安装，已尝试下载单文件视频格式；如平台只提供分离音视频，仍可能失败。"


def _success_message(warnings: list[str]) -> str:
    if warnings:
        return f"视频已下载；{'；'.join(warnings)}。"
    return "授权下载完成，已作为本地素材入库。"


def _join_logs(*parts: str) -> str:
    return "\n".join(part for part in parts if part)


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
