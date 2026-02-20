#!/usr/bin/env python3
"""
Search Claude Code conversation history.
Used by /history command to provide context for answering questions.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "claude_history.db"


def get_db():
    if not DB_PATH.exists():
        print("ERROR: Database not found. Run: python ~/.claude/scripts/history_index.py")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def search(query: str, limit: int = 15):
    """Search and return formatted context."""
    conn = get_db()

    results = conn.execute("""
        SELECT m.uuid, m.session_id, m.type, m.role, m.content, m.timestamp,
               s.project, s.git_branch,
               highlight(messages_fts, 1, '**', '**') as highlighted
        FROM messages_fts fts
        JOIN messages m ON fts.uuid = m.uuid
        LEFT JOIN sessions s ON m.session_id = s.session_id
        WHERE messages_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (query, limit)).fetchall()

    conn.close()

    if not results:
        return "No relevant conversation history found."

    output = []
    for r in results:
        ts = r["timestamp"][:10] if r["timestamp"] else "?"
        branch = r["git_branch"] or ""
        proj = Path(r["project"]).name if r["project"] else "?"
        role = r["role"] or r["type"]
        content = r["content"] or ""

        # Truncate very long content
        if len(content) > 1000:
            content = content[:1000] + "..."

        header = f"[{ts}] {role.upper()} in {proj}"
        if branch:
            header += f" ({branch})"

        output.append(f"{header}\n{content}")

    return "\n\n---\n\n".join(output)


def list_sessions(limit: int = 10):
    """List recent sessions."""
    conn = get_db()
    results = conn.execute("""
        SELECT session_id, project, git_branch, last_ts, message_count
        FROM sessions
        ORDER BY last_ts DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    output = ["Recent sessions:"]
    for r in results:
        proj = Path(r["project"]).name if r["project"] else "?"
        branch = r["git_branch"] or "-"
        ts = r["last_ts"][:10] if r["last_ts"] else "?"
        output.append(f"- {ts}: {proj} ({branch}) - {r['message_count']} msgs - id:{r['session_id'][:8]}")

    return "\n".join(output)


def show_session(session_prefix: str, limit: int = 50):
    """Show messages from a session."""
    conn = get_db()

    session = conn.execute("""
        SELECT session_id, project, git_branch FROM sessions WHERE session_id LIKE ?
    """, (f"{session_prefix}%",)).fetchone()

    if not session:
        return f"No session found matching '{session_prefix}'"

    messages = conn.execute("""
        SELECT type, role, content, timestamp
        FROM messages
        WHERE session_id = ?
        ORDER BY timestamp
        LIMIT ?
    """, (session["session_id"], limit)).fetchall()
    conn.close()

    proj = Path(session["project"]).name if session["project"] else "?"
    output = [f"Session in {proj} ({session['git_branch'] or '-'}):\n"]

    for m in messages:
        role = m["role"] or m["type"]
        content = m["content"] or ""
        if len(content) > 800:
            content = content[:800] + "..."
        output.append(f"**{role.upper()}**: {content}\n")

    return "\n".join(output)


def main():
    if len(sys.argv) < 2:
        print("Usage: history_search.py <search|sessions|show> [args]")
        return

    cmd = sys.argv[1]

    if cmd == "search" and len(sys.argv) > 2:
        print(search(" ".join(sys.argv[2:])))
    elif cmd == "sessions":
        print(list_sessions())
    elif cmd == "show" and len(sys.argv) > 2:
        print(show_session(sys.argv[2]))
    else:
        print("Usage: history_search.py <search|sessions|show> [args]")


if __name__ == "__main__":
    main()
