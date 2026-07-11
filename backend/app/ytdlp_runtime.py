from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import settings


def ytdlp_command() -> list[str] | None:
    configured = settings.ytdlp_path.strip()
    if configured:
        resolved = shutil.which(configured)
        if resolved:
            return [resolved]
        configured_path = Path(configured).expanduser()
        if configured_path.is_file():
            return [str(configured_path)]

    default_command = shutil.which("yt-dlp")
    if default_command:
        return [default_command]
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    return None


def require_ytdlp_command() -> list[str]:
    command = ytdlp_command()
    if command:
        return command
    raise RuntimeError("未找到 yt-dlp；请运行 npm run setup，或设置有效的 YTDLP_PATH。")


def ytdlp_status() -> tuple[bool, str]:
    command = ytdlp_command()
    if not command:
        return False, "未找到 yt-dlp 命令或 Python 模块。"
    try:
        completed = subprocess.run([*command, "--version"], capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return False, f"{' '.join(command)} 状态检查失败：{exc}"
    output = completed.stdout.strip() or completed.stderr.strip()
    label = " ".join(command)
    if completed.returncode != 0:
        return False, f"{label} 检查失败：{output or f'退出码 {completed.returncode}'}"
    return True, f"{label} ({output or '版本未知'})"
