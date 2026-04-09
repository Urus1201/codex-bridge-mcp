# Contributing

Thanks for your interest in contributing to codex-bridge-mcp!

## Getting Started

1. Fork the repo and clone it locally
2. Set up the development environment:

```bash
cd codex-bridge-mcp
uv venv
uv pip install "mcp[cli]>=1.9.0"
```

3. Make sure you have Codex CLI installed with at least one session in `~/.codex/`

## Making Changes

- Keep the server lightweight — it's a bridge, not a framework
- All data access must be read-only (never write to Codex's data files)
- Test with both interactive and `codex exec` session formats
- Support both Windows and Unix paths

## Pull Requests

1. Create a branch from `main`
2. Write clear commit messages
3. Test that `claude mcp list` shows the server as connected
4. Verify both `codex_list_sessions` and `codex_read_session` work with your changes
5. Open a PR with a description of what changed and why

## Reporting Issues

When filing an issue, please include:

- Your OS (Windows/macOS/Linux)
- Python version (`python --version`)
- Codex CLI version (`codex --version`)
- The MCP client you're using (Claude Code, Cursor, etc.)
- The error message or unexpected behavior

## Ideas for Contribution

- Support for additional Codex event types
- Session export to markdown
- Pagination for very large sessions
- Session search by date range
- Support for `codex exec` session format variations
