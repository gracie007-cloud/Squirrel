# Squirrel

Local-first memory system for AI coding tools. Learns your coding patterns and provides personalized, task-aware context to AI assistants via MCP.

## What It Does

Squirrel passively watches your development activity, extracts coding patterns and project knowledge, and feeds that context back to AI tools so they generate code matching your style.

```
You code with Claude Code / Codex / Cursor / Gemini CLI
                    ↓
    Squirrel watches logs and learns (passive)
                    ↓
    AI tools call MCP → get personalized context
                    ↓
          Better code suggestions
```

The more you code, the better Squirrel understands your preferences.

## Key Features

- **Task-Aware Context**: Returns relevant memory with "why this is relevant" explanations
- **User Style Memory**: Learns your coding preferences (async/await, type hints, testing patterns)
- **Project Knowledge**: Remembers project facts (framework, database, key endpoints)
- **Token-Efficient**: Budget-bounded outputs that fit any context window
- **Local-First**: All data stays on your machine via SQLite + sqlite-vec

## Quick Start

```bash
# Install
brew install sqrl

# Start daemon (one per machine)
sqrl daemon start

# Initialize a project
cd ~/my-project
sqrl init

# Done - Squirrel now watches and learns
```

## Architecture (v1)

Two processes working together via Unix socket IPC:

| Component | Language | Role |
|-----------|----------|------|
| **Rust Daemon** | Rust | Log watcher, SQLite storage, MCP server, CLI |
| **Memory Service** | Python | Router Agent (dual-mode), embeddings, retrieval |

```
┌─────────────────────────────────────────────────────────────────┐
│                        RUST DAEMON                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │Log Watch │  │ SQLite   │  │MCP Server│  │      CLI         ││
│  │(4 CLIs)  │  │sqlite-vec│  │(2 tools) │  │sqrl init/status  ││
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────────┘│
│       │             │             │                             │
│       └─────────────┴─────────────┴─────────────────────────────│
│                            ↕ IPC (Unix socket)                  │
└─────────────────────────────────────────────────────────────────┘
                             ↕
┌─────────────────────────────────────────────────────────────────┐
│                      PYTHON MEMORY SERVICE                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              Router Agent (Dual Mode)                      │ │
│  │  ┌─────────────────────┐  ┌─────────────────────────────┐ │ │
│  │  │   INGEST Mode       │  │      ROUTE Mode             │ │ │
│  │  │ events → memories   │  │ task → relevant memories    │ │ │
│  │  │ ADD/UPDATE/NOOP     │  │ + "why" explanations        │ │ │
│  │  └─────────────────────┘  └─────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Embeddings  │  │  Retrieval   │  │   "Why" Generator    │  │
│  │ (ONNX model) │  │ (similarity) │  │ (heuristic templates)│  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## MCP Tools (v1)

Squirrel exposes 2 MCP tools for AI assistants:

| Tool | Purpose |
|------|---------|
| `squirrel_get_task_context` | Task-aware memory with "why" explanations (primary) |
| `squirrel_search_memory` | Semantic search across all memory |

Both tools accept `max_tokens` to adapt output to any model's context size.

## How It Works

### Input: Passive Log Watching

```
~/.claude/projects/**/*.jsonl  ──┐
~/.codex-cli/logs/**/*.jsonl   ──┼──→ Rust Daemon ──→ Events ──→ Episodes
~/.gemini/logs/**/*.jsonl      ──┤                        ↓
~/.cursor-tutor/logs/**/*.jsonl──┘               Python INGEST mode
                                                         ↓
                                              ADD/UPDATE/NOOP memories
```

1. Rust watches log files from 4 supported CLIs
2. Parses logs into normalized Event structs
3. Groups events into Episodes (same repo + CLI + time window)
4. Sends to Python Router Agent (INGEST mode)
5. Router decides: ADD new memory, UPDATE existing, or NOOP

### Output: MCP Tools

```
AI calls squirrel_get_task_context("Add delete endpoint")
                    ↓
            Rust MCP Server
                    ↓ IPC
         Python ROUTE mode + Retrieval
                    ↓
      Returns relevant memories + "why" explanations
```

1. AI tool calls MCP tool with task description
2. Python retrieves memory candidates via embedding similarity
3. Router Agent (ROUTE mode) selects relevant memories
4. Generates "why" explanation for each using heuristic templates
5. Returns budget-bounded JSON response

## Example Output

```json
{
  "task": "Add a delete endpoint",
  "memories": [
    {
      "type": "user_style",
      "content": "Prefers async/await for I/O handlers",
      "why": "Relevant because you're adding an HTTP endpoint"
    },
    {
      "type": "project_fact",
      "content": "Uses pytest with fixtures for API tests",
      "why": "Relevant because this endpoint will need tests"
    }
  ],
  "tokens_used": 156
}
```

## CLI Commands

```bash
sqrl init              # Initialize project
sqrl config            # Set user_id, API keys
sqrl daemon start      # Start global daemon
sqrl daemon stop       # Stop daemon
sqrl status            # Show project memory state
sqrl mcp               # Run MCP server (called by AI tools)
```

## Data Model

### Memory Types (4 only)

| Type | Description | Example |
|------|-------------|---------|
| `user_style` | Coding preferences | "Prefers async/await" |
| `project_fact` | Project knowledge | "Uses PostgreSQL 15" |
| `pitfall` | Known issues | "API returns 500 on null user_id" |
| `recipe` | Common patterns | "Use repository pattern for DB access" |

### Storage

```
~/.sqrl/
├── config.toml        # Global config
├── squirrel.db        # Global SQLite (user_style memories)
└── logs/              # Daemon logs

<repo>/.sqrl/
├── squirrel.db        # Project SQLite (project memories)
└── config.toml        # Project overrides
```

## Configuration

```toml
# ~/.sqrl/config.toml
[user]
id = "alice"

[llm]
anthropic_api_key = "sk-ant-..."
default_model = "claude-sonnet-4-20250514"

[daemon]
socket_path = "/tmp/sqrl_router.sock"
```

## Documentation

- [Architecture Spec](docs/ARCHITECTURE.md) - Full technical design
- [Development Plan](docs/DEVELOPMENT_PLAN.md) - Implementation roadmap
- [Project Structure](docs/PROJECT_STRUCTURE.md) - Directory layout

## v1 Scope

**In:**
- Passive input: Claude Code, Codex CLI, Cursor, Gemini CLI logs
- 2 MCP tools: get_task_context, search_memory
- 4 memory types: user_style, project_fact, pitfall, recipe
- Dual-mode Router Agent (INGEST + ROUTE)
- Budget-bounded outputs with "why" explanations
- Local SQLite + sqlite-vec storage

**v2 (Future):**
- Hooks output for Claude Code / Gemini CLI
- File injection for AGENTS.md / GEMINI.md
- Cloud sync, team memory sharing
- Web dashboard

## License

AGPL-3.0
