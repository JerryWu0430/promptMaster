#!/usr/bin/env python3
"""
Index Claude Code conversation history into SQLite for querying.

Usage:
    python claude_history.py index          # Index all conversations
    python claude_history.py search "query" # Search conversations
    python claude_history.py sessions       # List recent sessions
    python claude_history.py show <session> # Show session messages
"""

import sqlite3
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

CLAUDE_DIR = Path.home() / ".claude"
DB_PATH = Path(__file__).parent / "claude_history.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables and FTS index."""
    conn = get_db()
    conn.executescript("""
        -- Sessions table
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            project TEXT,
            cwd TEXT,
            git_branch TEXT,
            first_ts TEXT,
            last_ts TEXT,
            message_count INTEGER DEFAULT 0
        );

        -- Messages table
        CREATE TABLE IF NOT EXISTS messages (
            uuid TEXT PRIMARY KEY,
            session_id TEXT,
            parent_uuid TEXT,
            type TEXT,  -- user, assistant, summary
            role TEXT,
            content TEXT,
            timestamp TEXT,
            model TEXT,
            tool_names TEXT,  -- comma-separated tool names used
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        -- FTS for content search
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            uuid,
            content,
            content='messages',
            content_rowid='rowid'
        );

        -- Triggers to keep FTS in sync
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

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
        CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(timestamp);
    """)
    conn.commit()
    conn.close()


def extract_content(message_obj) -> tuple[str, str, list]:
    """Extract text content from message object. Returns (content, model, tool_names)."""
    if not message_obj:
        return "", "", []

    content = message_obj.get("content", "")
    model = message_obj.get("model", "")
    tool_names = []

    # Handle array content (assistant messages with tool_use)
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_names.append(block.get("name", ""))
                elif block.get("type") == "tool_result":
                    text_parts.append(str(block.get("content", ""))[:500])  # Truncate tool results
        content = "\n".join(text_parts)

    return str(content), model, tool_names


def index_jsonl(filepath: Path, conn: sqlite3.Connection, stats: dict):
    """Index a single JSONL file."""
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

                # Track session metadata
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

                # Extract message content
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
    except Exception as e:
        stats["errors"] += 1
        return

    # Insert sessions
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

    # Insert messages
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


def cmd_index():
    """Index all JSONL files."""
    print(f"Initializing database at {DB_PATH}")
    init_db()

    conn = get_db()
    stats = {"files": 0, "sessions": 0, "messages": 0, "errors": 0}

    # Find all JSONL files
    jsonl_files = list(CLAUDE_DIR.rglob("*.jsonl"))
    print(f"Found {len(jsonl_files)} JSONL files")

    for i, filepath in enumerate(jsonl_files):
        if i % 50 == 0:
            print(f"Processing {i}/{len(jsonl_files)}...")
            conn.commit()
        index_jsonl(filepath, conn, stats)

    conn.commit()
    conn.close()

    print(f"\nIndexed: {stats['files']} files, {stats['sessions']} sessions, {stats['messages']} messages")
    if stats["errors"]:
        print(f"Errors: {stats['errors']}")


def cmd_search(query: str, limit: int = 20):
    """Search messages by content."""
    conn = get_db()

    results = conn.execute("""
        SELECT m.uuid, m.session_id, m.type, m.role, m.content, m.timestamp,
               s.project, s.git_branch,
               highlight(messages_fts, 1, '>>>', '<<<') as highlighted
        FROM messages_fts fts
        JOIN messages m ON fts.uuid = m.uuid
        LEFT JOIN sessions s ON m.session_id = s.session_id
        WHERE messages_fts MATCH ?
        ORDER BY m.timestamp DESC
        LIMIT ?
    """, (query, limit)).fetchall()

    if not results:
        print("No results found.")
        return

    for r in results:
        ts = r["timestamp"][:19] if r["timestamp"] else "?"
        branch = r["git_branch"] or "no-branch"
        proj = Path(r["project"]).name if r["project"] else "?"

        print(f"\n{'='*60}")
        print(f"[{ts}] {r['type']} | {proj} ({branch})")
        print(f"Session: {r['session_id'][:8]}...")
        print("-" * 40)
        # Show highlighted content, truncated
        content = r["highlighted"] or r["content"] or ""
        print(content[:500] + ("..." if len(content) > 500 else ""))

    print(f"\n{len(results)} results")
    conn.close()


def cmd_sessions(limit: int = 20):
    """List recent sessions."""
    conn = get_db()

    results = conn.execute("""
        SELECT session_id, project, git_branch, first_ts, last_ts, message_count
        FROM sessions
        ORDER BY last_ts DESC
        LIMIT ?
    """, (limit,)).fetchall()

    for r in results:
        proj = Path(r["project"]).name if r["project"] else "?"
        branch = r["git_branch"] or "-"
        ts = r["last_ts"][:16] if r["last_ts"] else "?"
        print(f"{r['session_id'][:12]}  {r['message_count']:4} msgs  {ts}  {proj[:20]:20}  {branch[:20]}")

    conn.close()


def cmd_show(session_prefix: str):
    """Show messages from a session."""
    conn = get_db()

    # Find matching session
    session = conn.execute("""
        SELECT session_id FROM sessions WHERE session_id LIKE ?
    """, (f"{session_prefix}%",)).fetchone()

    if not session:
        print(f"No session found matching '{session_prefix}'")
        return

    messages = conn.execute("""
        SELECT type, role, content, timestamp, tool_names
        FROM messages
        WHERE session_id = ?
        ORDER BY timestamp
    """, (session["session_id"],)).fetchall()

    print(f"Session: {session['session_id']}")
    print(f"Messages: {len(messages)}\n")

    for m in messages:
        ts = m["timestamp"][11:19] if m["timestamp"] else "?"
        role = m["role"] or m["type"]
        tools = f" [tools: {m['tool_names']}]" if m["tool_names"] else ""

        print(f"[{ts}] {role.upper()}{tools}")
        content = m["content"] or ""
        # Truncate long content
        if len(content) > 800:
            content = content[:800] + "...(truncated)"
        print(content)
        print()

    conn.close()


def cmd_stats():
    """Show database statistics."""
    conn = get_db()

    sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    user_msgs = conn.execute("SELECT COUNT(*) FROM messages WHERE type='user'").fetchone()[0]
    asst_msgs = conn.execute("SELECT COUNT(*) FROM messages WHERE type='assistant'").fetchone()[0]

    print(f"Database: {DB_PATH}")
    print(f"Sessions: {sessions}")
    print(f"Messages: {messages} (user: {user_msgs}, assistant: {asst_msgs})")

    conn.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "index":
        cmd_index()
    elif cmd == "search" and len(sys.argv) > 2:
        cmd_search(" ".join(sys.argv[2:]))
    elif cmd == "sessions":
        cmd_sessions()
    elif cmd == "show" and len(sys.argv) > 2:
        cmd_show(sys.argv[2])
    elif cmd == "stats":
        cmd_stats()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
