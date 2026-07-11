from __future__ import annotations

import re
from html import unescape
from pathlib import Path
from typing import Literal

import httpx

from app.config import settings
from app.db import get_connection, now_iso, row_to_dict
from app.media import cleanup_processed_media, extract_audio

LanguageCode = Literal["en", "zh"]
_ARGOS_LANGUAGE_CODES = {"en": ("en",), "zh": ("zh", "zt")}


def transcribe_and_translate(video_id: int) -> dict:
    with get_connection() as conn:
        video = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            return {"ok": False, "message": "视频不存在。"}
        assets = [row_to_dict(row) for row in conn.execute("SELECT * FROM media_assets WHERE video_id = ? ORDER BY id DESC", (video_id,)).fetchall()]

    raw_segments = _segments_from_imported_assets(video_id, assets)
    source = "imported_transcript"
    if not raw_segments:
        media_asset = next((asset for asset in assets if asset["kind"] == "media" and asset["stored_path"]), None)
        if media_asset and settings.cloud_ai_enabled and settings.openai_api_key:
            audio_path = extract_audio(media_asset["stored_path"], video_id)
            raw_segments = _transcribe_with_openai(audio_path)
            source = "openai_audio"
        elif media_asset and settings.local_asr_enabled:
            raw_segments = _transcribe_with_local_whisper(media_asset["stored_path"])
            source = "local_faster_whisper"
        else:
            raw_segments = _demo_segments(dict(video))
            source = "demo_generated"

    zh_segments = translate_segments_to_zh(raw_segments)
    save_transcript_segments(video_id, raw_segments, zh_segments, source, "translation", "translated")

    removed = cleanup_processed_media(video_id)
    return {
        "ok": True,
        "video_id": video_id,
        "source": source,
        "segments": len(raw_segments),
        "removed_media": removed,
        "message": "已生成双语字幕包。" if source != "demo_generated" else "未配置可用转写输入，已生成演示字幕用于验证流程。",
    }


def save_transcript_segments(
    video_id: int,
    en_segments: list[dict],
    zh_segments: list[dict],
    en_source: str,
    zh_source: str,
    status: str = "translated",
) -> None:
    timestamp = now_iso()
    with get_connection() as conn:
        conn.execute("DELETE FROM transcripts WHERE video_id = ?", (video_id,))
        for segment in en_segments:
            conn.execute(
                """
                INSERT INTO transcripts (video_id, language, start_seconds, end_seconds, text, source, created_at)
                VALUES (?, 'en', ?, ?, ?, ?, ?)
                """,
                (video_id, segment["start_seconds"], segment["end_seconds"], segment["text"], en_source, timestamp),
            )
        for segment in zh_segments:
            conn.execute(
                """
                INSERT INTO transcripts (video_id, language, start_seconds, end_seconds, text, source, created_at)
                VALUES (?, 'zh', ?, ?, ?, ?, ?)
                """,
                (video_id, segment["start_seconds"], segment["end_seconds"], segment["text"], zh_source, timestamp),
            )
        conn.execute("UPDATE videos SET status = ?, updated_at = ? WHERE id = ?", (status, timestamp, video_id))


def translate_segments_to_zh(segments: list[dict]) -> list[dict]:
    return _translate_segments(segments)


def _segments_from_imported_assets(video_id: int, assets: list[dict]) -> list[dict]:
    for asset in assets:
        text = asset.get("transcript_text", "")
        if not text:
            continue
        parsed = parse_transcript_text(text)
        if parsed:
            return parsed
    return []


def parse_transcript_text(text: str) -> list[dict]:
    text = text.strip()
    if not text:
        return []
    if "-->" in text:
        return _parse_timed_text(text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    segments = []
    cursor = 0.0
    for line in lines:
        duration = min(max(len(line.split()) * 0.45, 3.0), 8.0)
        segments.append({"start_seconds": cursor, "end_seconds": cursor + duration, "text": line})
        cursor += duration
    return segments


def normalize_transcript_segments(segments: list[dict]) -> list[dict]:
    return _collapse_rolling_subtitle_segments(segments)


def _parse_timed_text(text: str) -> list[dict]:
    lines = text.replace("\ufeff", "").splitlines()
    timing_indexes = [index for index, line in enumerate(lines) if "-->" in line]
    segments: list[dict] = []
    for position, timing_index in enumerate(timing_indexes):
        timing_line = lines[timing_index].strip()
        next_timing_index = timing_indexes[position + 1] if position + 1 < len(timing_indexes) else len(lines)
        body_lines = [line.strip() for line in lines[timing_index + 1 : next_timing_index] if line.strip()]
        if body_lines and body_lines[-1].isdigit():
            body_lines.pop()
        start_raw, end_raw = [part.strip().split(" ")[0] for part in timing_line.split("-->", 1)]
        body = _clean_subtitle_text(" ".join(body_lines))
        if body:
            segments.append(
                {
                    "start_seconds": _parse_timestamp(start_raw),
                    "end_seconds": _parse_timestamp(end_raw),
                    "text": body,
                }
            )
    return normalize_transcript_segments(segments)


def _collapse_rolling_subtitle_segments(segments: list[dict]) -> list[dict]:
    collapsed: list[dict] = []
    previous: dict | None = None
    for segment in segments:
        start = float(segment["start_seconds"])
        end = float(segment["end_seconds"])
        text = _clean_subtitle_text(segment.get("text", ""))
        if not text or end <= start:
            previous = {"start_seconds": start, "end_seconds": end, "text": text}
            continue

        novel_text = text
        if previous and start - float(previous["end_seconds"]) <= 0.08:
            previous_text = str(previous.get("text") or "")
            if end - start <= 0.05 and (text == previous_text or text in previous_text or previous_text in text):
                novel_text = ""
            elif text != previous_text:
                novel_text = _trim_rolling_overlap(previous_text, text)

        if novel_text:
            collapsed.append({"start_seconds": start, "end_seconds": end, "text": novel_text})
        previous = {"start_seconds": start, "end_seconds": end, "text": text}
    return collapsed


def _trim_rolling_overlap(previous: str, current: str) -> str:
    previous_tokens = previous.split()
    current_tokens = current.split()
    max_overlap = min(len(previous_tokens), len(current_tokens))
    for size in range(max_overlap, 0, -1):
        previous_tail = [token.casefold() for token in previous_tokens[-size:]]
        current_head = [token.casefold() for token in current_tokens[:size]]
        overlap_chars = sum(len(token) for token in current_tokens[:size])
        if previous_tail == current_head and (size >= 2 or overlap_chars >= 12):
            remainder = " ".join(current_tokens[size:]).strip()
            return remainder or current
    return current


def _parse_timestamp(value: str) -> float:
    normalized = value.replace(",", ".")
    parts = normalized.split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def _transcribe_with_openai(audio_path: Path) -> list[dict]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("CLOUD_AI_ENABLED=true 但未安装 OpenAI SDK。请运行：uv sync --project backend --extra cloud-ai") from exc

    client = OpenAI(api_key=settings.openai_api_key)
    with audio_path.open("rb") as audio:
        response = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio,
            response_format="verbose_json",
        )
    segments = []
    for item in getattr(response, "segments", []) or []:
        segments.append(
            {
                "start_seconds": float(item.get("start", 0)),
                "end_seconds": float(item.get("end", 0)),
                "text": item.get("text", "").strip(),
            }
        )
    if segments:
        return segments
    text = getattr(response, "text", "")
    return parse_transcript_text(text) or [{"start_seconds": 0, "end_seconds": 8, "text": text}]


def _transcribe_with_local_whisper(media_path: str) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("LOCAL_ASR_ENABLED=true 但未安装 faster-whisper。请安装 backend[local-asr]。") from exc

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(media_path)
    return [
        {"start_seconds": float(segment.start), "end_seconds": float(segment.end), "text": segment.text.strip()}
        for segment in segments
    ]


def _translate_segments(segments: list[dict]) -> list[dict]:
    if not segments:
        return []

    errors: list[str] = []
    if settings.argos_translate_enabled:
        try:
            return _translate_with_argos(segments)
        except Exception as exc:
            errors.append(f"Argos: {exc}")
    try:
        return _translate_with_ollama(segments)
    except Exception as exc:
        errors.append(f"Ollama: {exc}")
    if settings.cloud_ai_enabled and settings.openai_api_key and segments:
        try:
            return _translate_with_openai(segments)
        except Exception as exc:
            errors.append(f"OpenAI: {exc}")
    if settings.placeholder_translation_enabled:
        return [
            {
                "start_seconds": segment["start_seconds"],
                "end_seconds": segment["end_seconds"],
                "text": f"【中译】{segment['text']}",
            }
            for segment in segments
        ]
    detail = "；".join(errors) if errors else "未启用任何翻译引擎"
    raise RuntimeError(f"没有可用的中文翻译引擎。{detail}")


def _translate_with_argos(segments: list[dict]) -> list[dict]:
    try:
        import argostranslate.package
        import argostranslate.translate
    except ImportError as exc:
        raise RuntimeError("未安装 argostranslate，请安装本地翻译依赖。") from exc

    from_lang, to_lang = _get_argos_language_pair("en", "zh")
    if not from_lang or not to_lang:
        if not settings.argos_auto_install:
            raise RuntimeError("未安装 Argos 英文到中文模型，且 ARGOS_AUTO_INSTALL=false。")
        _install_argos_package("en", "zh")
        from_lang, to_lang = _get_argos_language_pair("en", "zh")
    if not from_lang or not to_lang:
        raise RuntimeError("未找到可用的 Argos 英文到中文模型。")

    translation = from_lang.get_translation(to_lang)
    translated = []
    for segment in segments:
        text = _clean_subtitle_text(segment["text"])
        translated_text = translation.translate(text).strip() if text else ""
        if not translated_text:
            translated_text = text
        translated.append(
            {
                "start_seconds": segment["start_seconds"],
                "end_seconds": segment["end_seconds"],
                "text": translated_text,
            }
        )
    return translated


def _get_argos_language_pair(from_code: LanguageCode, to_code: LanguageCode):
    import argostranslate.translate

    installed_languages = argostranslate.translate.get_installed_languages()
    from_lang = _find_argos_language(installed_languages, from_code)
    to_lang = _find_argos_language(installed_languages, to_code)
    return from_lang, to_lang


def _find_argos_language(languages: list, code: LanguageCode):
    codes = _ARGOS_LANGUAGE_CODES[code]
    return next((language for language in languages if language.code in codes), None)


def _install_argos_package(from_code: LanguageCode, to_code: LanguageCode) -> None:
    import argostranslate.package

    argostranslate.package.update_package_index()
    available_packages = argostranslate.package.get_available_packages()
    packages = [
        package
        for package in available_packages
        if package.from_code in _ARGOS_LANGUAGE_CODES[from_code] and package.to_code in _ARGOS_LANGUAGE_CODES[to_code]
    ]
    if not packages:
        raise RuntimeError("Argos 包索引中没有英文到中文模型。")
    package = packages[0]
    argostranslate.package.install_from_path(package.download())


def _clean_subtitle_text(text: str) -> str:
    text = re.sub(r"&\s*(amp|gt|lt|quot|apos)\s*;", r"&\1;", text, flags=re.IGNORECASE)
    text = unescape(text)
    text = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", text)
    text = re.sub(r"</?c>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s*>\s*>\s*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _translate_with_ollama(segments: list[dict]) -> list[dict]:
    numbered = "\n".join(f"{idx}. {segment['text']}" for idx, segment in enumerate(segments, start=1))
    prompt = (
        "你是科技公司 PR 使用的采访字幕翻译。请把下面英文逐行翻译成忠实顺读的中文，"
        "保留技术术语，不改写观点。只输出对应中文行，不要解释。\n\n"
        f"{numbered}"
    )
    response = httpx.post(
        f"{settings.ollama_base_url}/api/generate",
        json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    content = response.json().get("response", "")
    translated_lines = [line.strip() for line in content.splitlines() if line.strip()]
    clean_lines = [re.sub(r"^\d+[\.\、]\s*", "", line) for line in translated_lines]
    if len(clean_lines) != len(segments):
        raise ValueError("ollama translation line count mismatch")
    return [
        {
            "start_seconds": segment["start_seconds"],
            "end_seconds": segment["end_seconds"],
            "text": clean_lines[idx],
        }
        for idx, segment in enumerate(segments)
    ]


def _translate_with_openai(segments: list[dict]) -> list[dict]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("CLOUD_AI_ENABLED=true 但未安装 OpenAI SDK。请运行：uv sync --project backend --extra cloud-ai") from exc

    client = OpenAI(api_key=settings.openai_api_key)
    numbered = "\n".join(f"{idx}. {segment['text']}" for idx, segment in enumerate(segments, start=1))
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "你是科技公司 PR 使用的采访字幕翻译。忠实顺读，保留技术术语，不擅自改写观点。逐行输出中文，不要添加解释。",
            },
            {"role": "user", "content": numbered},
        ],
    )
    translated_lines = [line.strip() for line in response.choices[0].message.content.splitlines() if line.strip()]
    clean_lines = [re.sub(r"^\d+[\.\、]\s*", "", line) for line in translated_lines]
    if len(clean_lines) != len(segments):
        raise ValueError("translation line count mismatch")
    return [
        {
            "start_seconds": segment["start_seconds"],
            "end_seconds": segment["end_seconds"],
            "text": clean_lines[idx],
        }
        for idx, segment in enumerate(segments)
    ]


def _demo_segments(video: dict) -> list[dict]:
    title = video.get("title", "Technology interview")
    return [
        {
            "start_seconds": 0,
            "end_seconds": 6,
            "text": f"In this interview, the speaker frames the main theme: {title}.",
        },
        {
            "start_seconds": 6,
            "end_seconds": 14,
            "text": "The most useful PR takeaway is how the person connects product strategy with market timing.",
        },
        {
            "start_seconds": 14,
            "end_seconds": 23,
            "text": "This segment should be reviewed manually before any external clip is published.",
        },
    ]
