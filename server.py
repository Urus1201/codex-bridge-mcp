"""
Codex Bridge MCP Server
=======================
Exposes OpenAI Codex CLI session history to any MCP client (Claude Code,
Cursor, Windsurf, etc.) so you can search, read, and reference past Codex
conversations without leaving your editor.

Tools:
  - codex_list_sessions:  Search & list recorded Codex sessions
  - codex_read_session:   Read a full conversation by session ID

For *live chat* with Codex, pair this with the native Codex MCP server
(`codex mcp-server`) which exposes `codex` and `codex-reply` tools.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Codex stores data in ~/.codex by default; honour CODEX_HOME if set.
CODEX_DIR = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
STATE_DB = CODEX_DIR / "state_5.sqlite"
SESSIONS_DIR = CODEX_DIR / "sessions"

mcp = FastMCP("codex-bridge")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db() -> sqlite3.Connection:
    """Open the Codex state database (read-only)."""
    uri = f"file:{STATE_DB}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _ts_to_iso(ts: int | float | None) -> str:
    """Convert a Unix timestamp to an ISO-8601 string."""
    if ts is None:
        return "?"
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (OSError, ValueError):
        return str(ts)


def _find_session_file(session_id: str) -> Path | None:
    """Find the JSONL rollout file for a given session ID."""
    # Fast path: the DB stores the exact rollout path.
    if STATE_DB.exists():
        try:
            conn = _get_db()
            row = conn.execute(
                "SELECT rollout_path FROM threads WHERE id = ?", (session_id,)
            ).fetchone()
            conn.close()
            if row and row[0]:
                p = Path(row[0])
                if p.exists():
                    return p
        except sqlite3.Error:
            pass

    # Slow fallback: scan the sessions directory tree.
    if SESSIONS_DIR.exists():
        for jsonl_file in SESSIONS_DIR.rglob("*.jsonl"):
            if session_id in jsonl_file.name:
                return jsonl_file
    return None


def _parse_session_conversation(
    path: Path, max_messages: int = 50
) -> list[dict]:
    """
    Parse a Codex session JSONL file and extract the conversation
    (user messages, agent responses, tool calls, tool results).
    """
    messages: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = data.get("type")
            payload = data.get("payload", {})
            timestamp = data.get("timestamp", "")

            # --- User messages ---
            if (
                event_type == "event_msg"
                and payload.get("type") == "user_message"
            ):
                text = payload.get("message", "")
                if text:
                    messages.append(
                        {"role": "user", "text": text, "timestamp": timestamp}
                    )

            # --- Agent messages (two formats) ---
            # 1. event_msg  / agent_message  -> payload.message
            # 2. response_item / agent_message -> payload.text (exec sessions)
            elif (
                event_type == "event_msg"
                and payload.get("type") == "agent_message"
            ):
                text = payload.get("message", "")
                if text:
                    messages.append(
                        {"role": "codex", "text": text, "timestamp": timestamp}
                    )
            elif (
                event_type == "response_item"
                and payload.get("type") == "agent_message"
            ):
                text = payload.get("text", "")
                if text:
                    messages.append(
                        {"role": "codex", "text": text, "timestamp": timestamp}
                    )

            # --- Tool calls ---
            elif (
                event_type == "response_item"
                and payload.get("type") == "function_call"
            ):
                name = payload.get("name", "unknown")
                args_raw = payload.get("arguments", "")
                try:
                    args = json.loads(args_raw)
                    cmd = args.get("command", args_raw[:200])
                except (json.JSONDecodeError, TypeError):
                    cmd = str(args_raw)[:200]
                messages.append(
                    {
                        "role": "codex_tool",
                        "tool": name,
                        "command": cmd,
                        "timestamp": timestamp,
                    }
                )

            # --- Tool results ---
            elif (
                event_type == "event_msg"
                and payload.get("type") == "exec_command_end"
            ):
                output = payload.get("aggregated_output", "")
                exit_code = payload.get("exit_code", None)
                if output:
                    if len(output) > 2000:
                        output = (
                            output[:1000]
                            + f"\n...[{len(output) - 2000} chars truncated]"
                            + "...\n"
                            + output[-1000:]
                        )
                    messages.append(
                        {
                            "role": "tool_result",
                            "output": output,
                            "exit_code": exit_code,
                            "timestamp": timestamp,
                        }
                    )

            if len(messages) >= max_messages:
                break

    return messages


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def codex_list_sessions(
    keyword: str = "",
    limit: int = 20,
) -> str:
    """List recorded Codex CLI sessions.

    Queries the Codex state database for session threads, returning ID, title,
    model, working directory, and timestamps.

    Args:
        keyword: Optional keyword to filter sessions by title or first user
                 message (case-insensitive).
        limit: Maximum number of sessions to return (default 20, most recent
               first).
    """
    if not STATE_DB.exists():
        return "Codex state database not found at " + str(STATE_DB)

    conn = _get_db()
    if keyword:
        query = """
            SELECT id, title, model, cwd, created_at, updated_at,
                   first_user_message
            FROM threads
            WHERE (title LIKE ? OR first_user_message LIKE ?)
            ORDER BY updated_at DESC
            LIMIT ?
        """
        kw = f"%{keyword}%"
        rows = conn.execute(query, (kw, kw, limit)).fetchall()
    else:
        query = """
            SELECT id, title, model, cwd, created_at, updated_at,
                   first_user_message
            FROM threads
            ORDER BY updated_at DESC
            LIMIT ?
        """
        rows = conn.execute(query, (limit,)).fetchall()
    conn.close()

    if not rows:
        return "No sessions found." + (f" (filter: '{keyword}')" if keyword else "")

    lines = [f"Found {len(rows)} session(s):\n"]
    for sid, title, model, cwd, _created, updated, first_msg in rows:
        display = title or first_msg or "(no title)"
        if len(display) > 90:
            display = display[:87] + "..."
        updated_str = _ts_to_iso(updated)
        model_str = model or "?"
        lines.append(f"  {sid}")
        lines.append(f"    {updated_str}  |  model={model_str}  |  {display}")

    return "\n".join(lines)


@mcp.tool()
def codex_read_session(
    session_id: str,
    max_messages: int = 50,
    include_tool_calls: bool = True,
    include_tool_results: bool = False,
) -> str:
    """Read a Codex CLI session's conversation by session ID.

    Extracts user messages, Codex agent responses, and optionally tool
    calls/results from the session's JSONL log file.

    Args:
        session_id: The session UUID
                    (e.g., '019d6cdb-40ca-7d52-82e3-b13af6c88301').
        max_messages: Maximum number of conversation items to return
                      (default 50).
        include_tool_calls: Whether to include Codex's tool/shell calls
                            (default True).
        include_tool_results: Whether to include tool output/results
                              (default False — can be verbose).
    """
    # --- Metadata from DB ---
    title = "(unknown)"
    model = "?"
    cwd = "?"
    if STATE_DB.exists():
        try:
            conn = _get_db()
            row = conn.execute(
                "SELECT title, model, cwd, created_at, updated_at "
                "FROM threads WHERE id = ?",
                (session_id,),
            ).fetchone()
            conn.close()
            if row:
                title = row[0] or "(no title)"
                model = row[1] or "?"
                cwd = row[2] or "?"
        except sqlite3.Error:
            pass

    # --- Conversation from JSONL ---
    session_file = _find_session_file(session_id)
    if session_file is None:
        return (
            f"Session '{session_id}' not found. "
            "Use codex_list_sessions to find valid IDs."
        )

    messages = _parse_session_conversation(
        session_file, max_messages=max_messages * 3
    )

    filtered = []
    for msg in messages:
        role = msg["role"]
        if role in ("user", "codex"):
            filtered.append(msg)
        elif role == "codex_tool" and include_tool_calls:
            filtered.append(msg)
        elif role == "tool_result" and include_tool_results:
            filtered.append(msg)
    filtered = filtered[:max_messages]

    if not filtered:
        return (
            f"Session '{session_id}' found but contains no parseable "
            "conversation."
        )

    display_title = title if len(title) <= 120 else title[:117] + "..."

    lines = [
        f"Session: {session_id}",
        f"Title: {display_title}",
        f"Model: {model}",
        f"CWD: {cwd}",
        f"File: {session_file}",
        f"Messages: {len(filtered)}",
        "=" * 80,
        "",
    ]

    for msg in filtered:
        role = msg["role"]
        ts = msg.get("timestamp", "")[:19]

        if role == "user":
            text = msg["text"]
            if len(text) > 3000:
                text = (
                    text[:3000]
                    + f"\n...[truncated, {len(msg['text'])} total chars]"
                )
            lines.append(f"[{ts}] USER:\n{text}\n")

        elif role == "codex":
            text = msg["text"]
            if len(text) > 5000:
                text = (
                    text[:5000]
                    + f"\n...[truncated, {len(msg['text'])} total chars]"
                )
            lines.append(f"[{ts}] CODEX:\n{text}\n")

        elif role == "codex_tool":
            tool = msg.get("tool", "?")
            cmd = msg.get("command", "")
            lines.append(f"[{ts}] TOOL [{tool}]: {cmd}\n")

        elif role == "tool_result":
            output = msg.get("output", "")
            exit_code = msg.get("exit_code", "?")
            lines.append(f"[{ts}] RESULT (exit={exit_code}):\n{output}\n")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
