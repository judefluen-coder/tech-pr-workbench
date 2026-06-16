from __future__ import annotations

import re
from datetime import datetime, timezone

INTERVIEW_KEYWORDS = {
    "interview": 0.22,
    "conversation": 0.18,
    "podcast": 0.18,
    "talks with": 0.16,
    "fireside": 0.14,
    "keynote": 0.08,
    "full episode": 0.2,
    "deep dive": 0.16,
    "founder": 0.08,
    "ceo": 0.08,
    "采访": 0.24,
    "访谈": 0.24,
    "对谈": 0.2,
    "播客": 0.16,
    "独家对话": 0.22,
    "圆桌": 0.12,
    "炉边谈话": 0.14,
}

ORG_ALIAS_TERMS = {
    "01.ai",
    "alphabet",
    "amd",
    "anthropic",
    "baichuan",
    "chatglm",
    "claude",
    "cohere",
    "deep learning ai",
    "deeplearning.ai",
    "deepmind",
    "deepseek",
    "google",
    "google deepmind",
    "grok",
    "hugging face",
    "huggingface",
    "inflection",
    "kimi",
    "meta",
    "meta ai",
    "microsoft",
    "microsoft ai",
    "microsoft cto",
    "minimax",
    "mistral",
    "mistral ai",
    "moonshot ai",
    "nvidia",
    "openai",
    "qwen",
    "safe superintelligence",
    "scale ai",
    "ssi",
    "stanford hai",
    "stepfun",
    "tesla ai",
    "thinking machines lab",
    "tongyi",
    "xai",
    "zhipu ai",
    "智谱",
    "月之暗面",
    "通义",
    "豆包",
    "深度求索",
    "幻方",
    "海螺 ai",
    "百川智能",
    "阶跃星辰",
    "阿里通义",
    "零一万物",
}

GENERIC_NAME_TOKENS = {
    "ai",
    "artificial",
    "banks",
    "business",
    "characters",
    "company",
    "crisis",
    "engineer",
    "episode",
    "faang",
    "founder",
    "full",
    "future",
    "game",
    "genai",
    "how",
    "interview",
    "interviews",
    "learning",
    "llm",
    "network",
    "podcast",
    "preparation",
    "questions",
    "real",
    "roadmap",
    "strategy",
    "stay",
    "the",
    "theory",
    "top",
    "what",
    "when",
    "why",
    "world",
}

GENERIC_CJK_NAMES = {
    "人工智能",
    "公司",
    "创业",
    "大模型",
    "智能体",
    "机器人",
    "视频",
    "访谈",
    "对话",
    "高通",
}

NAME_PATTERN = r"[A-Z][A-Za-z.'’\-]*(?:[ \t]+[A-Z][A-Za-z.'’\-]*){1,3}"
PERSON_CANDIDATE_PATTERNS = (
    rf"\bsits down with\s+({NAME_PATTERN})",
    rf"\bspoke with\s+({NAME_PATTERN})",
    rf"\binterview with\s+({NAME_PATTERN})",
    rf"\bconversation with\s+({NAME_PATTERN})",
    rf"\bwith\s+({NAME_PATTERN})(?=[,|:\-]|(?:\s+(?:on|about|from|of)\b))",
    rf"\b({NAME_PATTERN})\s+Interview\b",
    rf"\bInterview\s+#?\d*:?\s+({NAME_PATTERN})(?=,|\||-|$)",
    rf"\bInterview Series:\s+({NAME_PATTERN})",
    rf"\b({NAME_PATTERN})\s*,\s*(?:Founder|Co-Founder|CEO|CTO|CIO|Chief|Professor|President|VP)\b",
    rf"[-–—|]\s*({NAME_PATTERN})\s*$",
)

CJK_CANDIDATE_PATTERNS = (
    r"(?:创始人|联合创始人|首席执行官|CEO|负责人|副总裁)([\u4e00-\u9fff]{2,4})(?:聊|谈|说|表示|称|：|:|，|,)",
    r"([\u4e00-\u9fff]{2,4})(?:接受|表示|称|谈|带着|回来了)",
    r"(?:和|与)(?:[\u4e00-\u9fffA-Za-z0-9·（）()]{0,16}?)([\u4e00-\u9fff]{2,4})(?:聊|对谈|访谈)",
)


def split_aliases(name: str, english_name: str = "", aliases: str = "") -> list[str]:
    values = [name, english_name]
    values.extend(part.strip() for part in re.split(r"[,，;/\n]", aliases or ""))
    return [item for item in dict.fromkeys(v.strip() for v in values if v.strip())]


def matched_people_for_video(title: str, description: str, people: list[dict], extra_text: str = "") -> list[dict]:
    title_text = title.lower()
    lead_text = _lead_description_text(description)
    context_text = f"{title}\n{description[:1200]}\n{extra_text[:1200]}".lower()
    matches: list[dict] = []
    for person in people:
        aliases = person_aliases_for_matching(person)
        if any(
            _alias_matches(alias, title_text)
            or _alias_matches(alias, lead_text)
            or _alias_matches_guest_context(alias, context_text)
            for alias in aliases
        ):
            matches.append(person)
    return matches


def _lead_description_text(description: str) -> str:
    clean = re.sub(r"\s+", " ", description or "").strip()
    if not clean:
        return ""
    first_sentence = re.split(r"(?<=[。！？.!?])\s+", clean, maxsplit=1)[0]
    return first_sentence[:320].lower()


def people_signals_for_video(
    title: str,
    description: str,
    channel_title: str,
    people: list[dict],
    transcript_text: str = "",
) -> tuple[list[dict], str, str, str]:
    matches = matched_people_for_video(title, description, people, f"{channel_title}\n{transcript_text}")
    matched_names = ", ".join(person["name"] for person in matches)
    channel_lower = channel_title.lower()
    candidates = [
        candidate
        for candidate in extract_candidate_people(title, description, transcript_text)
        if not channel_lower or candidate.lower() not in channel_lower
    ]
    candidate_people = matched_names or ", ".join(candidates)
    if matched_names:
        reason = "命中追踪人物名单"
    elif candidate_people:
        reason = "从标题、简介或字幕识别到采访嘉宾"
    else:
        reason = "标题、简介和已有字幕未识别到明确人物"
    return matches, matched_names, candidate_people, reason


def extract_candidate_people(title: str, description: str, transcript_text: str = "", limit: int = 4) -> list[str]:
    text = f"{title}\n{description}\n{transcript_text[:4000]}"
    candidates: list[str] = []
    for pattern in PERSON_CANDIDATE_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            _append_candidate(candidates, match.group(1), limit)
            if len(candidates) >= limit:
                return candidates
    for pattern in CJK_CANDIDATE_PATTERNS:
        for match in re.finditer(pattern, text):
            _append_candidate(candidates, match.group(1), limit)
            if len(candidates) >= limit:
                return candidates
    return candidates


def person_aliases_for_matching(person: dict) -> list[str]:
    aliases = split_aliases(person["name"], person.get("english_name", ""), person.get("aliases", ""))
    return [alias for alias in aliases if not _is_org_alias(alias)]


def _append_candidate(candidates: list[str], raw_value: str, limit: int) -> None:
    candidate = _clean_candidate_name(raw_value)
    if candidate and candidate not in candidates:
        candidates.append(candidate)
    if len(candidates) > limit:
        del candidates[limit:]


def _clean_candidate_name(value: str) -> str:
    candidate = re.sub(r"\s+", " ", value or "").strip(" \t\r\n-—–|:：,，.。'\"“”‘’()（）")
    if not candidate:
        return ""
    candidate = re.sub(r"\s+(?:on|about|from|of|at|for|and)\s+.*$", "", candidate, flags=re.IGNORECASE).strip()
    if re.search(r"[\u4e00-\u9fff]", candidate):
        return "" if candidate in GENERIC_CJK_NAMES or len(candidate) > 5 else candidate
    raw_tokens = [token.strip(".") for token in re.split(r"\s+", candidate) if token.strip(".")]
    if any(not token or not token[0].isupper() for token in raw_tokens):
        return ""
    tokens = [token.lower() for token in raw_tokens]
    if len(tokens) < 2 or len(tokens) > 4:
        return ""
    if any(token in GENERIC_NAME_TOKENS for token in tokens):
        return ""
    if _is_org_alias(candidate):
        return ""
    return candidate


def _is_org_alias(alias: str) -> bool:
    normalized = re.sub(r"\s+", " ", alias.lower().replace("·", " ")).strip()
    return normalized in ORG_ALIAS_TERMS


def _alias_matches(alias: str, haystack: str) -> bool:
    normalized = alias.lower().strip()
    if not normalized:
        return False
    if re.search(r"[\u4e00-\u9fff]", normalized):
        return normalized in haystack
    return re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", haystack) is not None


def _alias_matches_guest_context(alias: str, haystack: str) -> bool:
    normalized = alias.lower().strip()
    if not normalized:
        return False
    escaped = re.escape(normalized)
    if re.search(r"[\u4e00-\u9fff]", normalized):
        patterns = (
            rf"(?:对话|采访|访谈|专访|和|与).{{0,20}}{escaped}",
            rf"{escaped}.{{0,8}}(?:接受|表示|称|谈|聊|对谈|访谈)",
        )
    else:
        boundary = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        patterns = (
            rf"(?:with|interview with|conversation with|sits down with|spoke with)\s+{boundary}",
            rf"{boundary}\s*,?\s+(?:founder|co-founder|ceo|cto|cio|chief|professor|president|vp)\b",
            rf"{boundary}\s+(?:joins|talks|discusses|explains|on)\b",
        )
    return any(re.search(pattern, haystack) for pattern in patterns)


def interview_confidence(title: str, description: str, duration_seconds: int) -> float:
    text = f"{title}\n{description}".lower()
    score = 0.2
    for keyword, weight in INTERVIEW_KEYWORDS.items():
        if keyword in text:
            score += weight
    if duration_seconds >= 20 * 60:
        score += 0.2
    elif duration_seconds >= 8 * 60:
        score += 0.12
    if "shorts" in text or "短视频" in text or duration_seconds and duration_seconds < 120:
        score -= 0.18
    return max(0.0, min(score, 1.0))


def priority_score(
    matched_people: list[dict],
    confidence: float,
    published_at: str = "",
    channel_title: str = "",
    view_count: int = 0,
) -> float:
    people_score = max((p.get("priority", 3) for p in matched_people), default=1) / 5
    recency_score = _recency_score(published_at)
    channel_score = 0.08 if any(word in channel_title.lower() for word in ["ted", "decoder", "stanford", "y combinator", "the verge"]) else 0
    popularity = min(view_count / 250000, 1) * 0.08
    return round((people_score * 0.45 + confidence * 0.32 + recency_score * 0.15 + channel_score + popularity) * 100, 2)


def parse_youtube_duration(duration: str) -> int:
    pattern = re.compile(r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?")
    match = pattern.fullmatch(duration or "")
    if not match:
        return 0
    parts = {key: int(value or 0) for key, value in match.groupdict().items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


def _recency_score(published_at: str) -> float:
    if not published_at:
        return 0.2
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.2
    days = max((datetime.now(timezone.utc) - dt).days, 0)
    if days <= 1:
        return 1.0
    if days <= 7:
        return 0.65
    if days <= 30:
        return 0.35
    return 0.1
