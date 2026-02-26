"""
database.py — SQLite database with aiosqlite for async access.
"""
from __future__ import annotations

import aiosqlite
import os
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    display_name TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',
    online      INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS channels (
    channel_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    is_direct   INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS channel_members (
    channel_id  INTEGER REFERENCES channels(channel_id),
    user_id     INTEGER REFERENCES users(user_id),
    joined_at   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (channel_id, user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    message_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id       INTEGER REFERENCES users(user_id),
    channel_name    TEXT DEFAULT 'general',
    recipient_id    INTEGER DEFAULT NULL,
    message_type    TEXT DEFAULT 'text',
    plaintext       TEXT,
    ciphertext      TEXT,
    encryption_method TEXT DEFAULT 'none',
    key_id          TEXT DEFAULT NULL,
    timestamp       TEXT DEFAULT (datetime('now')),
    metadata        TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS key_pool (
    key_id          TEXT PRIMARY KEY,
    user_pair       TEXT NOT NULL,
    key_hex         TEXT NOT NULL,
    key_bits        INTEGER NOT NULL,
    status          TEXT DEFAULT 'active',
    qber            REAL DEFAULT 0.0,
    encryption_method TEXT DEFAULT 'otp',
    sha256          TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    used_at         TEXT DEFAULT NULL,
    session_id      TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS qkd_sessions (
    session_id          TEXT PRIMARY KEY,
    key_length_requested INTEGER,
    raw_count           INTEGER DEFAULT 0,
    lost_count          INTEGER DEFAULT 0,
    sifted_count        INTEGER DEFAULT 0,
    qber                REAL DEFAULT 0.0,
    eve_detected        INTEGER DEFAULT 0,
    final_key_bits      INTEGER DEFAULT 0,
    duration_ms         REAL DEFAULT 0.0,
    noise_depol         REAL DEFAULT 0.0,
    noise_loss          REAL DEFAULT 0.0,
    eve_active          INTEGER DEFAULT 0,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS security_alerts (
    alert_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT (datetime('now')),
    severity    TEXT DEFAULT 'info',
    message     TEXT,
    link_id     TEXT DEFAULT NULL,
    qber        REAL DEFAULT NULL,
    action      TEXT DEFAULT ''
);

-- Seed default channels
INSERT OR IGNORE INTO channels (name, is_direct) VALUES ('general', 0);
INSERT OR IGNORE INTO channels (name, is_direct) VALUES ('quantum-lab', 0);
INSERT OR IGNORE INTO channels (name, is_direct) VALUES ('alerts', 0);
"""


async def get_db() -> aiosqlite.Connection:
    """Get an async database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Initialize database schema."""
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()


async def seed_demo_users():
    """Create demo users Alice and Bob."""
    db = await get_db()
    try:
        users = [
            ("alice", "Alice (Sender)"),
            ("bob", "Bob (Receiver)"),
            ("eve", "Eve (Eavesdropper)"),
        ]
        for uname, dname in users:
            await db.execute(
                "INSERT OR IGNORE INTO users (username, display_name) VALUES (?, ?)",
                (uname, dname),
            )
        # Add demo users to general channel
        rows = await db.execute_fetchall("SELECT user_id FROM users")
        ch = await db.execute_fetchall("SELECT channel_id FROM channels WHERE name='general'")
        if ch:
            ch_id = ch[0][0]
            for row in rows:
                await db.execute(
                    "INSERT OR IGNORE INTO channel_members (channel_id, user_id) VALUES (?, ?)",
                    (ch_id, row[0]),
                )
        await db.commit()
    finally:
        await db.close()
