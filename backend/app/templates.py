from __future__ import annotations

import json
import re
import sqlite3

from app.db import get_connection, now_iso, row_to_dict

DEFAULT_TEMPLATE_SLUG = "ai-interviews"

JSON_FIELDS = {
    "youtube_queries",
    "bilibili_queries",
    "topic_terms",
    "scoring_terms",
    "highlight_terms",
}

BUILTIN_TEMPLATES = [
    {
        "slug": DEFAULT_TEMPLATE_SLUG,
        "name": "AI 采访",
        "page_title": "AI 采访日报",
        "description": "按日期区间追踪 AI 圈新增采访，保留原链，一键下载翻译后进入剪辑。",
        "list_title": "AI 采访列表",
        "run_button_label": "抓取区间 AI 采访",
        "empty_title": "还没有这个区间的真实采访候选",
        "empty_description": "点击抓取后，系统会按人物名单、AI 采访关键词和重点 B站账号搜索，并按真实发布时间过滤。",
        "search_placeholder": "搜人物、标题、频道",
        "summary_focus": "AI/科技趋势",
        "compliance_note": "自动发现只保存元数据和原始链接；下载剪辑前请确认素材授权。",
        "youtube_queries": [
            "AI interview",
            "artificial intelligence interview",
            "AI conversation",
            "AI podcast",
            "LLM interview",
            "fireside chat AI",
        ],
        "bilibili_queries": ["AI 采访", "人工智能 访谈", "大模型 访谈", "OpenAI 访谈", "Anthropic 访谈", "DeepSeek 访谈"],
        "topic_terms": [
            "ai",
            "artificial intelligence",
            "agi",
            "agent",
            "llm",
            "openai",
            "anthropic",
            "deepmind",
            "nvidia",
            "deepseek",
            "大模型",
            "智能体",
            "人工智能",
        ],
        "scoring_terms": {
            "interview": 0.22,
            "conversation": 0.18,
            "podcast": 0.18,
            "fireside": 0.14,
            "full episode": 0.2,
            "deep dive": 0.16,
            "采访": 0.24,
            "访谈": 0.24,
            "对谈": 0.2,
            "播客": 0.16,
        },
        "highlight_terms": [
            "agent",
            "agi",
            "openai",
            "deepseek",
            "nvidia",
            "model",
            "startup",
            "product",
            "safety",
            "智能体",
            "大模型",
            "开源",
            "商业化",
            "算力",
            "趋势",
        ],
        "is_builtin": 1,
    },
    {
        "slug": "tech-executive-interviews",
        "name": "科技高管访谈",
        "page_title": "科技高管访谈监测",
        "description": "追踪科技公司 CEO、CTO、创始人的访谈、峰会对话、财报采访和炉边谈话。",
        "list_title": "科技高管访谈列表",
        "run_button_label": "抓取区间高管访谈",
        "empty_title": "还没有这个区间的高管访谈候选",
        "empty_description": "点击抓取后，系统会按高管人物池、访谈关键词和重点来源搜索，并按真实发布时间过滤。",
        "search_placeholder": "搜高管、公司、标题、频道",
        "summary_focus": "高管观点、公司战略、资本市场表达",
        "compliance_note": "适合 PR 监测高管公开发声；下载剪辑前请确认素材授权。",
        "youtube_queries": [
            "CEO interview",
            "CTO interview",
            "founder interview",
            "earnings interview",
            "fireside chat CEO",
            "technology executive conversation",
        ],
        "bilibili_queries": ["科技 CEO 访谈", "创始人 访谈", "高管 对谈", "财报 采访", "科技公司 发布会 对话"],
        "topic_terms": [
            "ceo",
            "cto",
            "founder",
            "executive",
            "earnings",
            "strategy",
            "roadmap",
            "leadership",
            "创始人",
            "高管",
            "首席执行官",
            "战略",
            "财报",
            "路线图",
        ],
        "scoring_terms": {
            "interview": 0.2,
            "conversation": 0.16,
            "fireside": 0.18,
            "earnings": 0.16,
            "ceo": 0.14,
            "cto": 0.12,
            "founder": 0.14,
            "keynote": 0.08,
            "访谈": 0.22,
            "对谈": 0.18,
            "专访": 0.2,
            "财报": 0.14,
            "创始人": 0.12,
        },
        "highlight_terms": [
            "strategy",
            "roadmap",
            "growth",
            "market",
            "customers",
            "margin",
            "forecast",
            "战略",
            "路线图",
            "增长",
            "市场",
            "客户",
            "利润",
            "判断",
        ],
        "is_builtin": 1,
    },
    {
        "slug": "competitor-launches",
        "name": "竞品发布/演示",
        "page_title": "竞品发布监测",
        "description": "追踪竞品发布会、产品 demo、hands-on 评测、roadmap 和客户案例视频。",
        "list_title": "竞品发布与演示列表",
        "run_button_label": "抓取区间竞品视频",
        "empty_title": "还没有这个区间的竞品发布候选",
        "empty_description": "点击抓取后，系统会按公司/产品名单、发布演示关键词和重点来源搜索，并按真实发布时间过滤。",
        "search_placeholder": "搜公司、产品、标题、频道",
        "summary_focus": "竞品发布、产品能力、客户案例",
        "compliance_note": "适合竞品情报和内容拆解；下载剪辑前请确认素材授权。",
        "youtube_queries": [
            "product launch",
            "product demo",
            "hands on review",
            "roadmap update",
            "customer case study",
            "new feature demo",
        ],
        "bilibili_queries": ["产品发布", "产品演示", "竞品 评测", "功能 更新", "客户案例"],
        "topic_terms": [
            "launch",
            "demo",
            "hands on",
            "review",
            "roadmap",
            "feature",
            "case study",
            "release",
            "发布",
            "演示",
            "评测",
            "功能",
            "客户案例",
            "路线图",
        ],
        "scoring_terms": {
            "launch": 0.24,
            "demo": 0.22,
            "hands on": 0.18,
            "review": 0.16,
            "roadmap": 0.18,
            "release": 0.14,
            "new feature": 0.18,
            "case study": 0.14,
            "发布": 0.24,
            "演示": 0.22,
            "评测": 0.16,
            "功能": 0.14,
            "客户案例": 0.14,
        },
        "highlight_terms": [
            "new",
            "feature",
            "demo",
            "launch",
            "pricing",
            "customer",
            "workflow",
            "integration",
            "发布",
            "功能",
            "演示",
            "价格",
            "客户",
            "工作流",
            "集成",
        ],
        "is_builtin": 1,
    },
]


def init_builtin_templates(conn: sqlite3.Connection) -> None:
    timestamp = now_iso()
    for template in BUILTIN_TEMPLATES:
        values = _encode_template({**template, "created_at": timestamp, "updated_at": timestamp})
        conn.execute(
            """
            INSERT INTO topic_templates (
              slug, name, page_title, description, list_title, run_button_label,
              empty_title, empty_description, search_placeholder, summary_focus,
              compliance_note, youtube_queries, bilibili_queries, topic_terms,
              scoring_terms, highlight_terms, is_builtin, base_slug, created_at, updated_at
            )
            VALUES (
              :slug, :name, :page_title, :description, :list_title, :run_button_label,
              :empty_title, :empty_description, :search_placeholder, :summary_focus,
              :compliance_note, :youtube_queries, :bilibili_queries, :topic_terms,
              :scoring_terms, :highlight_terms, :is_builtin, :base_slug, :created_at, :updated_at
            )
            ON CONFLICT(slug) DO UPDATE SET
              name = excluded.name,
              page_title = excluded.page_title,
              description = excluded.description,
              list_title = excluded.list_title,
              run_button_label = excluded.run_button_label,
              empty_title = excluded.empty_title,
              empty_description = excluded.empty_description,
              search_placeholder = excluded.search_placeholder,
              summary_focus = excluded.summary_focus,
              compliance_note = excluded.compliance_note,
              youtube_queries = excluded.youtube_queries,
              bilibili_queries = excluded.bilibili_queries,
              topic_terms = excluded.topic_terms,
              scoring_terms = excluded.scoring_terms,
              highlight_terms = excluded.highlight_terms,
              is_builtin = 1,
              updated_at = excluded.updated_at
            WHERE topic_templates.is_builtin = 1
            """,
            {**values, "base_slug": template.get("base_slug", "")},
        )


def list_templates() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM topic_templates ORDER BY is_builtin DESC, slug ASC").fetchall()
        return [_decode_template(row_to_dict(row)) for row in rows]


def get_template(slug: str | None = None) -> dict:
    with get_connection() as conn:
        return get_template_from_conn(conn, slug)


def get_template_from_conn(conn: sqlite3.Connection, slug: str | None = None) -> dict:
    requested = slug or DEFAULT_TEMPLATE_SLUG
    row = conn.execute("SELECT * FROM topic_templates WHERE slug = ?", (requested,)).fetchone()
    if not row and requested != DEFAULT_TEMPLATE_SLUG:
        row = conn.execute("SELECT * FROM topic_templates WHERE slug = ?", (DEFAULT_TEMPLATE_SLUG,)).fetchone()
    if not row:
        fallback = {**BUILTIN_TEMPLATES[0], "created_at": now_iso(), "updated_at": now_iso(), "base_slug": ""}
        return fallback
    return _decode_template(row_to_dict(row))


def clone_template(source_slug: str, name: str = "", slug: str = "") -> dict:
    with get_connection() as conn:
        source = get_template_from_conn(conn, source_slug)
        new_slug = _unique_slug(conn, slug or f"{source['slug']}-copy")
        timestamp = now_iso()
        cloned = {
            **source,
            "slug": new_slug,
            "name": name.strip() or f"{source['name']} 副本",
            "page_title": f"{name.strip() or source['name']} 工作台",
            "is_builtin": 0,
            "base_slug": source["slug"],
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        conn.execute(
            """
            INSERT INTO topic_templates (
              slug, name, page_title, description, list_title, run_button_label,
              empty_title, empty_description, search_placeholder, summary_focus,
              compliance_note, youtube_queries, bilibili_queries, topic_terms,
              scoring_terms, highlight_terms, is_builtin, base_slug, created_at, updated_at
            )
            VALUES (
              :slug, :name, :page_title, :description, :list_title, :run_button_label,
              :empty_title, :empty_description, :search_placeholder, :summary_focus,
              :compliance_note, :youtube_queries, :bilibili_queries, :topic_terms,
              :scoring_terms, :highlight_terms, :is_builtin, :base_slug, :created_at, :updated_at
            )
            """,
            _encode_template(cloned),
        )
        _clone_people(conn, source["slug"], new_slug, timestamp)
        return get_template_from_conn(conn, new_slug)


def update_template(slug: str, updates: dict) -> dict:
    allowed = {
        "name",
        "page_title",
        "description",
        "list_title",
        "run_button_label",
        "empty_title",
        "empty_description",
        "search_placeholder",
        "summary_focus",
        "compliance_note",
        "youtube_queries",
        "bilibili_queries",
        "topic_terms",
        "scoring_terms",
        "highlight_terms",
    }
    values = {key: value for key, value in updates.items() if key in allowed and value is not None}
    if not values:
        return get_template(slug)
    values["updated_at"] = now_iso()
    encoded = _encode_template(values)
    assignments = ", ".join(f"{key} = :{key}" for key in encoded)
    with get_connection() as conn:
        existing = conn.execute("SELECT slug FROM topic_templates WHERE slug = ?", (slug,)).fetchone()
        if not existing:
            raise ValueError("主题模板不存在。")
        conn.execute(f"UPDATE topic_templates SET {assignments} WHERE slug = :slug", {**encoded, "slug": slug})
        return get_template_from_conn(conn, slug)


def _encode_template(template: dict) -> dict:
    encoded = dict(template)
    for field in JSON_FIELDS:
        if field in encoded:
            encoded[field] = json.dumps(encoded.get(field) or ([] if field != "scoring_terms" else {}), ensure_ascii=False)
    return encoded


def _decode_template(template: dict) -> dict:
    decoded = dict(template)
    for field in JSON_FIELDS:
        value = decoded.get(field)
        if isinstance(value, str):
            try:
                decoded[field] = json.loads(value) if value else ([] if field != "scoring_terms" else {})
            except json.JSONDecodeError:
                decoded[field] = [] if field != "scoring_terms" else {}
    decoded["is_builtin"] = int(decoded.get("is_builtin") or 0)
    return decoded


def _unique_slug(conn: sqlite3.Connection, raw_slug: str) -> str:
    base = re.sub(r"[^a-z0-9-]+", "-", raw_slug.lower()).strip("-") or "custom-template"
    slug = base
    index = 2
    while conn.execute("SELECT 1 FROM topic_templates WHERE slug = ?", (slug,)).fetchone():
        slug = f"{base}-{index}"
        index += 1
    return slug


def _clone_people(conn: sqlite3.Connection, source_slug: str, target_slug: str, timestamp: str) -> None:
    rows = conn.execute("SELECT name, english_name, aliases, priority, notes FROM people WHERE template_slug = ?", (source_slug,)).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT INTO people (template_slug, name, english_name, aliases, priority, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (target_slug, row["name"], row["english_name"], row["aliases"], row["priority"], row["notes"], timestamp, timestamp),
        )
