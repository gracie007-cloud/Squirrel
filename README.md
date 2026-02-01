# Squirrel

Memory layer for AI coding agents. Local-first, no AI in Squirrel itself.

## Why Squirrel

- **AI learns your style.** Preferences and decisions persist across sessions.
- **Mistakes remembered.** Past errors become future prevention.
- **Docs stay fresh.** Git hooks detect when docs need updates.
- **Zero overhead.** No daemon, no background process. Runs only when called.

## How It Works

```
You code with AI → AI decides what's worth remembering
        ↓
AI calls MCP: squirrel_store_memory
        ↓
Squirrel stores to local SQLite
        ↓
Next session: AI calls squirrel_get_memory → context restored
```

Squirrel has **no AI**. Your CLI tool (Claude Code, Cursor, etc.) has full conversation context and decides what to store. Squirrel is just storage + git hooks.

## Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `preference` | Coding style | "No emojis in code or commits" |
| `project` | Project knowledge | "Use httpx not requests" |
| `decision` | Architecture choices | "Chose SQLite for local storage" |
| `solution` | Problem-solution pairs | "Fixed SSL by switching to httpx" |

## Doc Debt Detection

Git hooks track when code changes but related docs don't.

```
You commit .rs code → post-commit hook checks mappings
    → specs/ARCHITECTURE.md not updated? → doc debt recorded
You push → pre-push hook warns about pending debt
```

## Quick Start

```bash
# Initialize in any project
cd ~/my-project
sqrl init
```

`sqrl init` automatically:
- Creates `.sqrl/` with config and database
- Installs git hooks for doc debt tracking
- Registers MCP server with your AI tool
- Adds memory triggers to CLAUDE.md

## CLI

| Command | Description |
|---------|-------------|
| `sqrl init` | Initialize project |
| `sqrl status` | Show memories and doc debt |
| `sqrl goaway` | Remove all Squirrel data |
| `sqrl mcp-serve` | Start MCP server (called by AI tool) |

## Supported Tools

Claude Code (others coming)

## Architecture

```
CLI AI (Claude Code, Cursor, etc.)
    │ MCP
    ▼
sqrl binary (Rust)
    │
    ▼
SQLite (.sqrl/memory.db)
```

Single Rust binary. No daemon, no Python, no LLM calls, no network.

| Component | Responsibility |
|-----------|----------------|
| sqrl binary | MCP server, CLI, git hooks, SQLite storage |
| CLI AI | Decides what to remember, fixes doc debt |

## Development

```bash
git clone https://github.com/anthropics/squirrel.git
cd squirrel
devenv shell

cargo test    # Run tests
cargo build   # Build binary
```

## License

AGPL-3.0
