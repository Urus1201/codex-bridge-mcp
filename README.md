# codex-bridge-mcp

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![MCP Protocol](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

> **Bridge between Claude Code and OpenAI Codex CLI** — search, read, and reference your Codex session history from any MCP client.

```
You: "Read my Codex session about the auth refactor and continue where it left off"

Claude Code: [calls codex_read_session] -> reads full Codex conversation -> continues the work
```

---

## The Problem

If you use both **Claude Code** and **Codex CLI**, your work is split across two disconnected histories. Neither agent knows what the other did. You end up copy-pasting context between them, or worse, re-explaining everything from scratch.

## The Solution

This MCP server gives any MCP client (Claude Code, Cursor, Windsurf, etc.) read access to your local Codex session history. No API keys needed — everything is local.

```
┌─────────────┐     MCP (stdio)     ┌──────────────────┐     read-only     ┌─────────────┐
│ Claude Code  │ ◄────────────────► │ codex-bridge-mcp │ ◄──────────────► │ ~/.codex/    │
│ Cursor       │                    │                  │                   │  state.sqlite│
│ Windsurf     │                    │  list sessions   │                   │  sessions/   │
│ any MCP      │                    │  read sessions   │                   │  *.jsonl     │
│  client      │                    │                  │                   │              │
└─────────────┘                     └──────────────────┘                   └─────────────┘
```

## Tools

| Tool | Description |
|---|---|
| `codex_list_sessions` | Search & list Codex sessions by keyword, with model/timestamp/title metadata |
| `codex_read_session` | Read a full conversation (user messages, agent responses, tool calls) by session ID |

## Example Output

### Listing sessions

```
> "List Codex sessions about authentication"

Found 3 session(s):

  019d6cdb-40ca-7d52-82e3-b13af6c88301
    2026-04-08 17:46:43  |  model=gpt-5.4  |  Review the auth middleware for compliance issues...
  019d5437-4891-7052-a803-ccdfd2554a81
    2026-04-03 16:40:30  |  model=gpt-5.4  |  Refactor OAuth token handling to use rotating keys...
  019c364a-fa80-7b92-9bfc-c3e7cb1031ed
    2026-03-15 09:22:11  |  model=gpt-4.1  |  Add session-based auth to the API gateway...
```

### Reading a session

```
> "Read Codex session 019d6cdb-40ca-7d52-82e3-b13af6c88301"

Session: 019d6cdb-40ca-7d52-82e3-b13af6c88301
Title: Review the auth middleware for compliance issues
Model: gpt-5.4
CWD: D:\Local\Work\my-project
Messages: 12
================================================================================

[2026-04-08T11:30:07] USER:
Review the auth middleware for compliance issues with token storage...

[2026-04-08T11:30:45] CODEX:
I've reviewed the middleware. Here are the key findings...

[2026-04-08T11:31:02] TOOL [shell_command]: rg -n "session.*token" src/auth/
...
```

## Quick Start

### Prerequisites

- Python 3.11+
- [OpenAI Codex CLI](https://github.com/openai/codex) installed with at least one session in `~/.codex/`

### Install in Claude Code

**One-liner** (no clone needed):

```bash
claude mcp add --transport stdio --scope user codex-bridge -- \
  uvx --from "mcp[cli]" mcp run /path/to/server.py
```

**With a dedicated venv:**

```bash
git clone https://github.com/Urus1201/codex-bridge-mcp.git
cd codex-bridge-mcp
uv venv && uv pip install "mcp[cli]>=1.9.0"

# Linux/macOS
claude mcp add --transport stdio --scope user codex-bridge -- \
  "$(pwd)/.venv/bin/python" "$(pwd)/server.py"

# Windows (Git Bash)
claude mcp add --transport stdio --scope user codex-bridge -- \
  "$(cygpath -w .venv/Scripts/python.exe)" "$(cygpath -w server.py)"
```

### Install in `.mcp.json` (Claude Desktop, Cursor, etc.)

```json
{
  "mcpServers": {
    "codex-bridge": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run", "--with", "mcp[cli]",
        "python", "/absolute/path/to/codex-bridge-mcp/server.py"
      ]
    }
  }
}
```

<details>
<summary><b>Windows paths</b></summary>

```json
{
  "mcpServers": {
    "codex-bridge": {
      "type": "stdio",
      "command": "C:\\path\\to\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\codex-bridge-mcp\\server.py"]
    }
  }
}
```

</details>

## Recommended: Pair with native Codex MCP server

This server handles **reading history**. For **live chat** with Codex (including multi-turn conversations), also add the native Codex MCP server:

```bash
claude mcp add --transport stdio --scope user codex -- codex mcp-server
```

This gives you the full bridge:

| Server | Tools | Use for |
|---|---|---|
| `codex-bridge` | `codex_list_sessions`, `codex_read_session` | Searching & reading past sessions |
| `codex` (native) | `codex`, `codex-reply` | Live chat with Codex, multi-turn by thread ID |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `CODEX_HOME` | `~/.codex` | Path to the Codex data directory |

## How it works

Codex CLI stores all session data locally:

- **`~/.codex/state_5.sqlite`** — thread metadata (ID, title, model, timestamps, working directory)
- **`~/.codex/sessions/YYYY/MM/DD/*.jsonl`** — full conversation logs in JSONL format

This server reads both (read-only, never writes) to reconstruct conversations. It handles two Codex event formats:

1. `event_msg/agent_message` — standard interactive responses
2. `response_item/agent_message` — exec/batch session format

No data leaves your machine. No API keys required. Everything is local.

## Origin Story

This project was born from a real collaboration session between Claude Code (Opus 4.6) and Codex CLI (GPT-5) — two AI agents that needed to read each other's work. The first version was hacked together in one evening to solve a concrete problem: Claude Code couldn't access a Codex conversation about interval velocity modeling, and copy-pasting wasn't going to cut it.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
