#!/usr/bin/env python3
"""
Index Claude Code conversation history into SQLite.
Run this periodically to keep the database up to date.
"""

import sqlite3
import json
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
DB_PATH = CLAUDE_DIR / "claude_history.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            project TEXT,
            cwd TEXT,
            git_branch TEXT,
            first_ts TEXT,
            last_ts TEXT,
            message_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS messages (
            uuid TEXT PRIMARY KEY,
            session_id TEXT,
            parent_uuid TEXT,
            type TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT,
            model TEXT,
            tool_names TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            uuid,
            content,
            content='messages',
            content_rowid='rowid'
        );

        CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(uuid, content) VALUES (new.uuid, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, uuid, content) VALUES('delete', old.uuid, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, uuid, content) VALUES('delete', old.uuid, old.content);
            INSERT INTO messages_fts(uuid, content) VALUES (new.uuid, new.content);
        END;

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
        CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);
    """)
    conn.commit()
    conn.close()


def extract_content(message_obj):
    if not message_obj:
        return "", "", []

    content = message_obj.get("content", "")
    model = message_obj.get("model", "")
    tool_names = []

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_names.append(block.get("name", ""))
                elif block.get("type") == "tool_result":
                    text_parts.append(str(block.get("content", ""))[:500])
        content = "\n".join(text_parts)

    return str(content), model, tool_names


def index_jsonl(filepath, conn, stats):
    session_data = {}
    messages = []

    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")
                if entry_type not in ("user", "assistant", "summary"):
                    continue

                session_id = entry.get("sessionId", "")
                if not session_id:
                    continue

                if session_id not in session_data:
                    session_data[session_id] = {
                        "project": entry.get("cwd", ""),
                        "cwd": entry.get("cwd", ""),
                        "git_branch": entry.get("gitBranch", ""),
                        "first_ts": entry.get("timestamp", ""),
                        "last_ts": entry.get("timestamp", ""),
                        "count": 0
                    }
                else:
                    session_data[session_id]["last_ts"] = entry.get("timestamp", "")
                session_data[session_id]["count"] += 1

                msg_obj = entry.get("message", {})
                content, model, tool_names = extract_content(msg_obj)

                messages.append({
                    "uuid": entry.get("uuid", ""),
                    "session_id": session_id,
                    "parent_uuid": entry.get("parentUuid", ""),
                    "type": entry_type,
                    "role": msg_obj.get("role", ""),
                    "content": content,
                    "timestamp": entry.get("timestamp", ""),
                    "model": model,
                    "tool_names": ",".join(tool_names)
                })
    except Exception:
        stats["errors"] += 1
        return

    for sid, sdata in session_data.items():
        conn.execute("""
            INSERT INTO sessions (session_id, project, cwd, git_branch, first_ts, last_ts, message_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                last_ts = MAX(last_ts, excluded.last_ts),
                message_count = message_count + excluded.message_count
        """, (sid, sdata["project"], sdata["cwd"], sdata["git_branch"],
              sdata["first_ts"], sdata["last_ts"], sdata["count"]))
        stats["sessions"] += 1

    for msg in messages:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO messages
                (uuid, session_id, parent_uuid, type, role, content, timestamp, model, tool_names)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg["uuid"], msg["session_id"], msg["parent_uuid"], msg["type"],
                  msg["role"], msg["content"], msg["timestamp"], msg["model"], msg["tool_names"]))
            stats["messages"] += 1
        except Exception:
            pass

    stats["files"] += 1


def main():
    print(f"Initializing database at {DB_PATH}")
    init_db()

    conn = get_db()
    stats = {"files": 0, "sessions": 0, "messages": 0, "errors": 0}

    jsonl_files = list(CLAUDE_DIR.rglob("*.jsonl"))
    print(f"Found {len(jsonl_files)} JSONL files")

    for i, filepath in enumerate(jsonl_files):
        if i % 100 == 0:
            print(f"Processing {i}/{len(jsonl_files)}...")
            conn.commit()
        index_jsonl(filepath, conn, stats)

    conn.commit()
    conn.close()

    print(f"\nIndexed: {stats['files']} files, {stats['messages']} messages")
    if stats["errors"]:
        print(f"Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
