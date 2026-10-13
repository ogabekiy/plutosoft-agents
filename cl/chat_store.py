"""Persist incoming customer messages and assistant replies for the inbox UI."""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "conversation_history.sqlite3"
_initialize_lock = threading.Lock()
_initialized_path: Path | None = None


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    global _initialized_path
    if _initialized_path == DATABASE_PATH:
        return
    with _initialize_lock:
        if _initialized_path == DATABASE_PATH:
            return
        with _connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL CHECK (platform IN ('Instagram', 'Telegram')),
                    external_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('customer', 'assistant')),
                    text TEXT NOT NULL,
                    message_key TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (platform, external_id, message_key)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS messages_conversation_idx
                ON messages (platform, external_id, id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_profiles (
                    platform TEXT NOT NULL CHECK (platform IN ('Instagram', 'Telegram')),
                    external_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    username TEXT,
                    avatar_file_id TEXT,
                    profile_url TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (platform, external_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    lead_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL CHECK (platform IN ('Instagram', 'Telegram')),
                    source_user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    notification_status TEXT NOT NULL DEFAULT 'not_configured'
                        CHECK (notification_status IN ('not_configured', 'pending', 'sent', 'failed')),
                    notification_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            lead_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(leads)")
            }
            if "summary" not in lead_columns:
                connection.execute(
                    "ALTER TABLE leads ADD COLUMN summary TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS leads_created_idx ON leads (created_at DESC)"
            )
        _initialized_path = DATABASE_PATH


def update_profile(
    *,
    platform: str,
    external_id: str,
    display_name: str,
    username: str | None = None,
    avatar_file_id: str | None = None,
    profile_url: str | None = None,
) -> None:
    if platform not in {"Instagram", "Telegram"}:
        raise ValueError("Unsupported platform.")
    initialize()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO conversation_profiles (
                platform, external_id, display_name, username,
                avatar_file_id, profile_url, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, external_id) DO UPDATE SET
                display_name = CASE WHEN excluded.display_name != ''
                    THEN excluded.display_name ELSE conversation_profiles.display_name END,
                username = COALESCE(excluded.username, conversation_profiles.username),
                avatar_file_id = COALESCE(excluded.avatar_file_id, conversation_profiles.avatar_file_id),
                profile_url = COALESCE(excluded.profile_url, conversation_profiles.profile_url),
                updated_at = excluded.updated_at
            """,
            (
                platform,
                str(external_id),
                display_name.strip(),
                username.strip() if username else None,
                avatar_file_id,
                profile_url,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_profile(platform: str, external_id: str) -> dict | None:
    if platform not in {"Instagram", "Telegram"}:
        raise ValueError("Unsupported platform.")
    initialize()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT platform, external_id, display_name, username,
                   avatar_file_id, profile_url, updated_at
            FROM conversation_profiles
            WHERE platform = ? AND external_id = ?
            """,
            (platform, str(external_id)),
        ).fetchone()
    return dict(row) if row else None


def record_message(
    *,
    platform: str,
    external_id: str,
    display_name: str,
    role: str,
    text: str,
    message_key: str | None = None,
) -> None:
    if not text.strip():
        return
    initialize()
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO messages (
                platform, external_id, display_name, role, text, message_key, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                platform,
                str(external_id),
                display_name.strip() or str(external_id),
                role,
                text,
                message_key,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def list_conversations(platform: str = "all", search: str = "", limit: int = 150) -> list[dict]:
    initialize()
    filters = []
    values: list[object] = []
    if platform in {"Instagram", "Telegram"}:
        filters.append("platform = ?")
        values.append(platform)
    if search:
        filters.append("(display_name LIKE ? OR external_id LIKE ? OR text LIKE ?)")
        match = f"%{search}%"
        values.extend((match, match, match))
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    values.append(limit)
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT platform, external_id,
                   COALESCE(
                       NULLIF((SELECT display_name FROM conversation_profiles profile
                               WHERE profile.platform = messages.platform
                                 AND profile.external_id = messages.external_id), ''),
                       (SELECT display_name FROM messages customer
                        WHERE customer.platform = messages.platform
                          AND customer.external_id = messages.external_id
                          AND customer.role = 'customer'
                        ORDER BY customer.id DESC LIMIT 1)
                   ) AS display_name,
                   (SELECT username FROM conversation_profiles profile
                    WHERE profile.platform = messages.platform
                      AND profile.external_id = messages.external_id) AS username,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM conversation_profiles profile
                       WHERE profile.platform = messages.platform
                         AND profile.external_id = messages.external_id
                         AND (profile.profile_url IS NOT NULL OR profile.avatar_file_id IS NOT NULL)
                   ) THEN '/dashboard/api/avatar/' || messages.platform || '/' || messages.external_id
                   ELSE NULL END AS avatar_url,
                   MAX(created_at) AS last_activity,
                   (SELECT text FROM messages latest
                    WHERE latest.platform = messages.platform
                      AND latest.external_id = messages.external_id
                    ORDER BY latest.id DESC LIMIT 1) AS last_message,
                   COUNT(*) AS message_count
            FROM messages
            {where}
            GROUP BY platform, external_id
            ORDER BY MAX(id) DESC
            LIMIT ?
            """,
            values,
        ).fetchall()
    return [dict(row) for row in rows]


def list_messages(platform: str, external_id: str, limit: int = 300) -> list[dict]:
    if platform not in {"Instagram", "Telegram"}:
        raise ValueError("Unsupported platform.")
    initialize()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT role, display_name, text, created_at
            FROM (
                SELECT id, role, display_name, text, created_at
                FROM messages
                WHERE platform = ? AND external_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (platform, external_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_stats() -> dict[str, int]:
    initialize()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                COUNT(DISTINCT CASE WHEN platform = 'Instagram' THEN external_id END) AS instagram,
                COUNT(DISTINCT CASE WHEN platform = 'Telegram' THEN external_id END) AS telegram,
                COUNT(*) AS messages
            FROM messages
            """
        ).fetchone()
        lead_count = connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    stats = dict(rows)
    stats["leads"] = lead_count
    return stats


def save_lead(
    *,
    lead_id: str,
    platform: str,
    source_user_id: str,
    name: str,
    phone: str,
    note: str,
    summary: str = "",
    notification_status: str = "pending",
) -> None:
    if platform not in {"Instagram", "Telegram"}:
        raise ValueError("Unsupported lead source.")
    if notification_status not in {"not_configured", "pending", "sent", "failed"}:
        raise ValueError("Unsupported notification status.")
    initialize()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO leads (
                lead_id, platform, source_user_id, name, phone, note, summary,
                notification_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lead_id) DO UPDATE SET
                summary = excluded.summary,
                notification_status = excluded.notification_status,
                updated_at = excluded.updated_at
            """,
            (
                lead_id,
                platform,
                str(source_user_id),
                name.strip(),
                phone.strip(),
                note.strip(),
                summary.strip(),
                notification_status,
                now,
                now,
            ),
        )


def update_lead_notification(
    lead_id: str,
    status: str,
    error: str | None = None,
) -> None:
    if status not in {"not_configured", "pending", "sent", "failed"}:
        raise ValueError("Unsupported notification status.")
    initialize()
    with _connect() as connection:
        connection.execute(
            """
            UPDATE leads
            SET notification_status = ?, notification_error = ?, updated_at = ?
            WHERE lead_id = ?
            """,
            (status, error, datetime.now(timezone.utc).isoformat(), lead_id),
        )


def list_leads(search: str = "", limit: int = 500) -> list[dict]:
    initialize()
    values: list[object] = []
    where = ""
    if search:
        where = (
            "WHERE name LIKE ? OR phone LIKE ? OR note LIKE ? "
            "OR summary LIKE ? OR platform LIKE ?"
        )
        term = f"%{search}%"
        values.extend((term, term, term, term, term))
    values.append(limit)
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT lead_id, platform, source_user_id, name, phone, note, summary,
                   notification_status, notification_error, created_at
            FROM leads
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            values,
        ).fetchall()
    return [dict(row) for row in rows]
