from __future__ import annotations

import importlib.util
import shutil
import subprocess

import httpx

from app.config import settings


def system_status() -> dict:
    ffmpeg_path = shutil.which("ffmpeg")
    yt_dlp_ok, yt_dlp_version = _module_version("yt_dlp")
    argos_ok, argos_message = _argos_status()
    ollama_ok, ollama_message = _ollama_status()
    return {
        "youtube_api": {
            "ok": bool(settings.youtube_api_key),
            "label": "YouTube Data API",
            "message": "已配置，可用官方免费配额发现公开视频。" if settings.youtube_api_key else "未配置，将优先用本机 yt-dlp 搜索。",
        },
        "yt_dlp": {
            "ok": yt_dlp_ok,
            "label": "yt-dlp",
            "message": yt_dlp_version if yt_dlp_ok else "未安装，无法本机搜索或授权下载。",
        },
        "ffmpeg": {
            "ok": bool(ffmpeg_path),
            "label": "FFmpeg",
            "message": ffmpeg_path or "未安装，无法抽音频和转码。",
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


def _module_version(module: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["python", "-m", module, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return False, str(exc)
    if completed.returncode != 0:
        return False, completed.stderr.strip()
    return True, completed.stdout.strip()


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
