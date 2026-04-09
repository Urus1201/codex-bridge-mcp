"""Tests for codex-bridge-mcp server."""

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import _ts_to_iso, _parse_session_conversation


def test_ts_to_iso_valid():
    result = _ts_to_iso(1712592000)
    assert "2024" in result
    assert ":" in result


def test_ts_to_iso_none():
    assert _ts_to_iso(None) == "?"


def test_ts_to_iso_zero():
    result = _ts_to_iso(0)
    assert result == "1970-01-01 00:00:00"


def test_parse_empty_file():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        f.write("")
        path = Path(f.name)

    messages = _parse_session_conversation(path)
    assert messages == []
    path.unlink()


def test_parse_user_message():
    event = {
        "type": "event_msg",
        "payload": {"type": "user_message", "message": "Hello Codex"},
        "timestamp": "2026-04-08T11:30:07.497Z",
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        f.write(json.dumps(event) + "\n")
        path = Path(f.name)

    messages = _parse_session_conversation(path)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["text"] == "Hello Codex"
    path.unlink()


def test_parse_agent_message_event_msg():
    event = {
        "type": "event_msg",
        "payload": {"type": "agent_message", "message": "Hello from Codex"},
        "timestamp": "2026-04-08T11:30:15.000Z",
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        f.write(json.dumps(event) + "\n")
        path = Path(f.name)

    messages = _parse_session_conversation(path)
    assert len(messages) == 1
    assert messages[0]["role"] == "codex"
    assert messages[0]["text"] == "Hello from Codex"
    path.unlink()


def test_parse_agent_message_response_item():
    event = {
        "type": "response_item",
        "payload": {"type": "agent_message", "text": "Response via exec"},
        "timestamp": "2026-04-08T11:30:15.000Z",
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        f.write(json.dumps(event) + "\n")
        path = Path(f.name)

    messages = _parse_session_conversation(path)
    assert len(messages) == 1
    assert messages[0]["role"] == "codex"
    assert messages[0]["text"] == "Response via exec"
    path.unlink()


def test_parse_tool_call():
    event = {
        "type": "response_item",
        "payload": {
            "type": "function_call",
            "name": "shell_command",
            "arguments": '{"command": "ls -la"}',
        },
        "timestamp": "2026-04-08T11:30:20.000Z",
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        f.write(json.dumps(event) + "\n")
        path = Path(f.name)

    messages = _parse_session_conversation(path)
    assert len(messages) == 1
    assert messages[0]["role"] == "codex_tool"
    assert messages[0]["tool"] == "shell_command"
    assert messages[0]["command"] == "ls -la"
    path.unlink()


def test_parse_max_messages():
    events = []
    for i in range(10):
        events.append({
            "type": "event_msg",
            "payload": {"type": "user_message", "message": f"msg {i}"},
            "timestamp": f"2026-04-08T11:30:{i:02d}.000Z",
        })

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
        path = Path(f.name)

    messages = _parse_session_conversation(path, max_messages=3)
    assert len(messages) == 3
    path.unlink()


def test_parse_full_conversation():
    """Test parsing a realistic multi-turn conversation."""
    events = [
        {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": "Fix the auth bug"},
            "timestamp": "2026-04-08T11:30:00.000Z",
        },
        {
            "type": "event_msg",
            "payload": {"type": "agent_message", "message": "I'll look into it."},
            "timestamp": "2026-04-08T11:30:05.000Z",
        },
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "shell_command",
                "arguments": '{"command": "rg session_token src/"}',
            },
            "timestamp": "2026-04-08T11:30:10.000Z",
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "exec_command_end",
                "aggregated_output": "src/auth.py:42: session_token = ...",
                "exit_code": 0,
            },
            "timestamp": "2026-04-08T11:30:12.000Z",
        },
        {
            "type": "event_msg",
            "payload": {"type": "agent_message", "message": "Found it. Fixing now."},
            "timestamp": "2026-04-08T11:30:15.000Z",
        },
    ]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
        path = Path(f.name)

    messages = _parse_session_conversation(path)
    assert len(messages) == 5
    assert [m["role"] for m in messages] == [
        "user", "codex", "codex_tool", "tool_result", "codex"
    ]
    path.unlink()
