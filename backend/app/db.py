from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from app.config import settings


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    settings.ensure_dirs()
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS topic_templates (
              slug TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              page_title TEXT NOT NULL,
              description TEXT DEFAULT '',
              list_title TEXT DEFAULT '',
              run_button_label TEXT DEFAULT '',
              empty_title TEXT DEFAULT '',
              empty_description TEXT DEFAULT '',
              search_placeholder TEXT DEFAULT '',
              summary_focus TEXT DEFAULT '',
              compliance_note TEXT DEFAULT '',
              youtube_queries TEXT DEFAULT '[]',
              bilibili_queries TEXT DEFAULT '[]',
              topic_terms TEXT DEFAULT '[]',
              scoring_terms TEXT DEFAULT '{}',
              highlight_terms TEXT DEFAULT '[]',
              is_builtin INTEGER NOT NULL DEFAULT 0,
              base_slug TEXT DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS people (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              template_slug TEXT NOT NULL DEFAULT 'ai-interviews',
              name TEXT NOT NULL,
              english_name TEXT DEFAULT '',
              aliases TEXT DEFAULT '',
              priority INTEGER NOT NULL DEFAULT 3,
              notes TEXT DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(template_slug) REFERENCES topic_templates(slug) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS source_queries (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              template_slug TEXT NOT NULL DEFAULT 'ai-interviews',
              person_id INTEGER,
              platform TEXT NOT NULL DEFAULT 'youtube',
              query TEXT NOT NULL,
              last_run_at TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(template_slug) REFERENCES topic_templates(slug) ON DELETE CASCADE,
              FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS videos (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              template_slug TEXT NOT NULL DEFAULT 'ai-interviews',
              platform TEXT NOT NULL DEFAULT 'youtube',
              external_id TEXT NOT NULL,
              url TEXT NOT NULL,
              title TEXT NOT NULL,
              description TEXT DEFAULT '',
              channel_title TEXT DEFAULT '',
              published_at TEXT DEFAULT '',
              duration_seconds INTEGER NOT NULL DEFAULT 0,
              view_count INTEGER NOT NULL DEFAULT 0,
              like_count INTEGER NOT NULL DEFAULT 0,
              thumbnail_url TEXT DEFAULT '',
              matched_people TEXT DEFAULT '',
              candidate_people TEXT DEFAULT '',
              people_match_reason TEXT DEFAULT '',
              interview_confidence REAL NOT NULL DEFAULT 0,
              priority_score REAL NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'new',
              compliance_note TEXT NOT NULL DEFAULT 'metadata_only',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(platform, external_id)
            );

            CREATE TABLE IF NOT EXISTS video_template_links (
              video_id INTEGER NOT NULL,
              template_slug TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY(video_id, template_slug),
              FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE,
              FOREIGN KEY(template_slug) REFERENCES topic_templates(slug) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS media_assets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              video_id INTEGER NOT NULL,
              kind TEXT NOT NULL,
              original_filename TEXT DEFAULT '',
              stored_path TEXT DEFAULT '',
              transcript_text TEXT DEFAULT '',
              authorization_note TEXT NOT NULL,
              delete_after_processing INTEGER NOT NULL DEFAULT 1,
              processing_status TEXT NOT NULL DEFAULT 'imported',
              created_at TEXT NOT NULL,
              FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS transcripts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              video_id INTEGER NOT NULL,
              language TEXT NOT NULL,
              start_seconds REAL NOT NULL,
              end_seconds REAL NOT NULL,
              text TEXT NOT NULL,
              source TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS clip_marks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              video_id INTEGER NOT NULL,
              start_seconds REAL NOT NULL,
              end_seconds REAL NOT NULL,
              label TEXT NOT NULL,
              note TEXT DEFAULT '',
              quote TEXT DEFAULT '',
              status TEXT NOT NULL DEFAULT 'draft',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS jobs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              type TEXT NOT NULL,
              status TEXT NOT NULL,
              message TEXT DEFAULT '',
              payload TEXT DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS download_tasks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              video_id INTEGER NOT NULL,
              engine TEXT NOT NULL,
              status TEXT NOT NULL,
              authorization_note TEXT NOT NULL,
              output_path TEXT DEFAULT '',
              log TEXT DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(video_id) REFERENCES videos(id) ON DELETE CASCADE
            );
            """
        )
        _ensure_column(conn, "people", "template_slug", "TEXT NOT NULL DEFAULT 'ai-interviews'")
        _ensure_column(conn, "source_queries", "template_slug", "TEXT NOT NULL DEFAULT 'ai-interviews'")
        _ensure_column(conn, "videos", "template_slug", "TEXT NOT NULL DEFAULT 'ai-interviews'")
        _ensure_column(conn, "videos", "summary", "TEXT DEFAULT ''")
        _ensure_column(conn, "videos", "source_tier", "TEXT NOT NULL DEFAULT 'stable'")
        _ensure_column(conn, "videos", "last_error", "TEXT DEFAULT ''")
        _ensure_column(conn, "videos", "candidate_people", "TEXT DEFAULT ''")
        _ensure_column(conn, "videos", "people_match_reason", "TEXT DEFAULT ''")
        from app.templates import DEFAULT_TEMPLATE_SLUG, init_builtin_templates

        init_builtin_templates(conn)
        conn.execute("UPDATE people SET template_slug = ? WHERE template_slug = '' OR template_slug IS NULL", (DEFAULT_TEMPLATE_SLUG,))
        conn.execute("UPDATE source_queries SET template_slug = ? WHERE template_slug = '' OR template_slug IS NULL", (DEFAULT_TEMPLATE_SLUG,))
        conn.execute("UPDATE videos SET template_slug = ? WHERE template_slug = '' OR template_slug IS NULL", (DEFAULT_TEMPLATE_SLUG,))
        conn.execute(
            """
            INSERT OR IGNORE INTO video_template_links (video_id, template_slug, created_at)
            SELECT id, template_slug, ? FROM videos
            """,
            (now_iso(),),
        )
        _refresh_people_signals(conn)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _refresh_people_signals(conn: sqlite3.Connection) -> None:
    from app.scoring import people_signals_for_video, priority_score
    from app.summaries import build_discovery_summary
    from app.templates import DEFAULT_TEMPLATE_SLUG, get_template_from_conn

    videos = conn.execute("SELECT * FROM videos").fetchall()
    for row in videos:
        video = row_to_dict(row)
        template_slug = video.get("template_slug") or DEFAULT_TEMPLATE_SLUG
        people = [dict(person) for person in conn.execute("SELECT * FROM people WHERE template_slug = ?", (template_slug,)).fetchall()]
        template = get_template_from_conn(conn, template_slug)
        matches, matched_names, candidate_people, reason = people_signals_for_video(
            video.get("title", ""),
            video.get("description", ""),
            video.get("channel_title", ""),
            people,
        )
        score = priority_score(
            matches,
            float(video.get("interview_confidence") or 0),
            video.get("published_at", ""),
            video.get("channel_title", ""),
            int(video.get("view_count") or 0),
        )
        summary = build_discovery_summary(
            video.get("title", ""),
            video.get("description", ""),
            video.get("channel_title", ""),
            matched_names or candidate_people,
            template,
        )
        conn.execute(
            """
            UPDATE videos
            SET matched_people = ?, candidate_people = ?, people_match_reason = ?,
                priority_score = ?, summary = ?, updated_at = ?
            WHERE id = ?
            """,
            (matched_names, candidate_people, reason, score, summary, now_iso(), video["id"]),
        )
