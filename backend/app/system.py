from __future__ import annotations

import importlib.util
import shutil
import subprocess

import httpx

from app.config import settings
from app.opencli_runtime import opencli_path
from app.ytdlp_runtime import ytdlp_status


def system_status() -> dict:
    ffmpeg_path = shutil.which("ffmpeg")
    yt_dlp_ok, yt_dlp_version = ytdlp_status()
    opencli_ok, opencli_message = _opencli_status()
    argos_ok, argos_message = _argos_status()
    ollama_ok, ollama_message = _ollama_status()
    return {
        "youtube_api": {
            "ok": bool(settings.youtube_api_key),
            "label": "YouTube Data API",
            "message": "已配置，可用官方免费配额发现公开视频。" if settings.youtube_api_key else "未配置，将依次尝试 opencli 和本机 yt-dlp 搜索。",
        },
        "yt_dlp": {
            "ok": yt_dlp_ok,
            "label": "yt-dlp",
            "message": yt_dlp_version,
        },
        "opencli": {
            "ok": opencli_ok,
            "label": "OpenCLI Browser Bridge",
            "message": opencli_message,
        },
        "ffmpeg": {
            "ok": bool(ffmpeg_path),
            "label": "FFmpeg",
            "message": ffmpeg_path or "未安装，下载会尝试单文件格式，但抽音频、合并和导出视频会受限。",
        },
        "argos": {
            "ok": argos_ok,
            "label": "Argos 本地翻译",
            "message": argos_message,
        },
        "ollama": {
            "ok": ollama_ok,
            "label": "Ollama 本地翻译",
            "message": ollama_message,
        },
        "local_asr": {
            "ok": settings.local_asr_enabled,
            "label": "本地 Whisper 转写",
            "message": "已启用 LOCAL_ASR_ENABLED。" if settings.local_asr_enabled else "未启用。可先用字幕/文本稿，或启用本地 Whisper。",
        },
        "cloud_ai": {
            "ok": settings.cloud_ai_enabled and bool(settings.openai_api_key),
            "label": "云端 AI 增强",
            "message": "已显式启用，会产生外部 API 调用。" if settings.cloud_ai_enabled else "默认关闭，不会产生额外付费 AI 调用。",
        },
    }


def _opencli_status() -> tuple[bool, str]:
    opencli = opencli_path()
    if not opencli:
        return False, "未找到 opencli 命令。"
    try:
        completed = subprocess.run([opencli, "daemon", "status"], capture_output=True, text=True, timeout=5)
    except Exception as exc:
        return False, f"OpenCLI 状态检查失败：{exc}"
    output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
    if completed.returncode != 0:
        return False, output or "OpenCLI daemon 未运行；抓取时会尝试唤醒。"
    if "Extension: connected" in output:
        return True, f"已连接；窗口模式 {settings.opencli_window_mode or 'default'}，preflight {'开启' if settings.opencli_preflight_enabled else '关闭'}。"
    return False, output or "OpenCLI daemon 已运行，但 Chrome 扩展未连接。"


def _argos_status() -> tuple[bool, str]:
    if not settings.argos_translate_enabled:
        return False, "已关闭 ARGOS_TRANSLATE_ENABLED。"
    if importlib.util.find_spec("argostranslate") is None:
        return False, "未安装 argostranslate；英文字幕无法用 Argos 本地翻译。"
    try:
        import argostranslate.translate

        languages = argostranslate.translate.get_installed_languages()
        codes = {language.code for language in languages}
        if "en" in codes and ("zh" in codes or "zt" in codes):
            return True, "已安装 Argos，可用于英文字幕本地翻译中文。"
        if settings.argos_auto_install:
            return True, "Argos 已安装，首次翻译会自动下载英中模型。"
        return False, "Argos 已安装，但缺少英中模型，且 ARGOS_AUTO_INSTALL=false。"
    except Exception as exc:
        return False, f"Argos 状态检查失败：{exc}"


def _ollama_status() -> tuple[bool, str]:
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=1.5)
        response.raise_for_status()
        models = [item.get("name") for item in response.json().get("models", [])]
        if settings.ollama_model in models:
            return True, f"已连接 {settings.ollama_model}。"
        if models:
            return True, f"已连接 Ollama，但未发现 {settings.ollama_model}。当前模型：{', '.join(models[:3])}"
        return True, "Ollama 已连接，但暂无模型。"
    except Exception:
        return False, "未连接 Ollama；会优先使用原中文字幕或 Argos 本地翻译。"
