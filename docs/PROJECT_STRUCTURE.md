# Project Structure (v1)

Complete directory layout and file responsibilities for Squirrel v1 architecture.

## v1 Architecture Components

```
RUST DAEMON                           PYTHON MEMORY SERVICE
├── Log watcher (4 CLIs)              ├── Router Agent (dual-mode)
├── SQLite + sqlite-vec storage       │   ├── INGEST: events → memories
├── MCP server (2 tools)              │   └── ROUTE: task → relevant memories
├── CLI (sqrl commands)               ├── ONNX embeddings (384-dim)
└── IPC client                        ├── Retrieval + "why" generation
         ↕ Unix socket IPC            └── IPC server
```

## Root Layout

```
Squirrel/
├── agent/                  # Rust daemon + CLI + MCP
├── memory_service/         # Python Router Agent + embeddings
├── docs/                   # Documentation
├── reference/              # Competitor analysis (gitignored clones)
├── .claude/                # Claude Code config
├── .cursorrules            # Cursor config
├── AGENTS.md               # Codex CLI config
├── GEMINI.md               # Gemini CLI config
├── LICENSE                 # AGPL-3.0
└── README.md               # Main documentation
```

## Rust Agent Module (`agent/`)

```
agent/
├── Cargo.toml              # Dependencies: tokio, rusqlite, sqlite-vec, notify, clap
├── Cargo.lock
├── src/
│   ├── main.rs             # Entry point: CLI command router
│   ├── lib.rs              # Shared library exports
│   │
│   ├── daemon.rs           # Daemon process management
│   │   ├── Daemon struct   # Main daemon state
│   │   ├── start()         # Spawn watchers + Python service
│   │   ├── stop()          # Graceful shutdown
│   │   └── batch_loop()    # Events → Episodes → IPC
│   │
│   ├── watcher.rs          # Multi-CLI log watching
│   │   ├── LogWatcher      # Watch log directories
│   │   ├── ClaudeParser    # ~/.claude/projects/**/*.jsonl
│   │   ├── CodexParser     # ~/.codex-cli/logs/**/*.jsonl
│   │   ├── GeminiParser    # ~/.gemini/logs/**/*.jsonl
│   │   ├── CursorParser    # ~/.cursor-tutor/logs/**/*.jsonl
│   │   └── parse_line()    # JSONL → Event
│   │
│   ├── events.rs           # Event and Episode models
│   │   ├── Event struct    # {id, cli, repo, event_type, content, timestamp}
│   │   ├── Episode struct  # {id, repo, cli, event_ids, start_ts, end_ts}
│   │   ├── CLI enum        # claude_code, codex, cursor, gemini
│   │   ├── compute_hash()  # Deduplication
│   │   └── group_episodes() # Same repo + CLI + time gap < 20min
│   │
│   ├── storage.rs          # SQLite + sqlite-vec
│   │   ├── init_global_db()   # ~/.sqrl/squirrel.db
│   │   ├── init_project_db()  # <repo>/.sqrl/squirrel.db
│   │   ├── save_events()
│   │   ├── save_episodes()
│   │   ├── save_memory()      # With embedding blob
│   │   ├── query_memories()   # Via sqlite-vec
│   │   └── SCHEMA            # memories, events, episodes tables
│   │
│   ├── ipc.rs              # Unix socket client to Python
│   │   ├── IpcClient       # Connect to /tmp/sqrl_router.sock
│   │   ├── router_agent()  # Call INGEST or ROUTE mode
│   │   └── fetch_memories() # Get memories for MCP tools
│   │
│   ├── mcp.rs              # MCP stdio server (2 tools)
│   │   ├── McpServer       # MCP protocol handler
│   │   ├── squirrel_get_task_context()  # Primary tool
│   │   ├── squirrel_search_memory()     # Search tool
│   │   └── run_stdio()     # Blocks on stdin/stdout
│   │
│   ├── cli.rs              # CLI commands
│   │   ├── cmd_init()      # Create .sqrl/, register project
│   │   ├── cmd_config()    # Set user_id, API keys
│   │   ├── cmd_daemon()    # start/stop/status
│   │   ├── cmd_status()    # Show memory stats
│   │   └── cmd_mcp()       # Run MCP server
│   │
│   ├── config.rs           # Configuration
│   │   ├── Config struct   # {user_id, api_key, socket_path}
│   │   ├── load_config()   # From ~/.sqrl/config.toml
│   │   ├── save_config()
│   │   └── get_projects()  # Registered repos
│   │
│   └── utils.rs            # Path helpers
│       ├── get_sqrl_dir()  # ~/.sqrl/
│       ├── get_project_sqrl_dir() # <repo>/.sqrl/
│       └── find_repo_root() # Walk up to .git/
│
└── tests/
    ├── integration/
    │   ├── daemon_test.rs
    │   ├── watcher_test.rs
    │   └── mcp_test.rs
    └── unit/
        ├── events_test.rs
        ├── storage_test.rs
        └── ipc_test.rs
```

## Python Memory Service (`memory_service/`)

```
memory_service/
├── pyproject.toml          # Dependencies: onnxruntime, anthropic, pydantic
├── README.md
├── models/                 # ONNX model files
│   └── all-MiniLM-L6-v2.onnx  # 25MB, 384-dim embeddings
│
├── squirrel_memory/
│   ├── __init__.py
│   │
│   ├── server.py           # Unix socket IPC server
│   │   ├── start_server()  # Listen on /tmp/sqrl_router.sock
│   │   ├── handle_request() # Route to router_agent or fetch_memories
│   │   └── read_write_json() # JSON-RPC style protocol
│   │
│   ├── router_agent.py     # Dual-mode Router Agent (core logic)
│   │   ├── router_agent()  # Entry point
│   │   ├── ingest_mode()   # Episode → ADD/UPDATE/NOOP + memory
│   │   │   └── "Is this a memorable pattern? What type?"
│   │   ├── route_mode()    # Task + candidates → selected + why
│   │   │   └── "Which memories are relevant? Why?"
│   │   └── PROMPTS         # LLM prompts for both modes
│   │
│   ├── embeddings.py       # ONNX embedding model
│   │   ├── EmbeddingModel  # Load all-MiniLM-L6-v2.onnx
│   │   ├── embed()         # text → 384-dim vector
│   │   └── batch_embed()   # Multiple texts
│   │
│   ├── retrieval.py        # Memory retrieval
│   │   ├── retrieve_candidates() # Query sqlite-vec
│   │   └── generate_why()  # Heuristic templates for "why" explanations
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── memory.py       # Memory, Event, Episode models
│   │   └── ipc.py          # RouterAgentRequest, FetchMemoriesRequest
│   │
│   └── llm.py              # LLM client wrapper
│       ├── LLMClient       # Unified client
│       ├── call_anthropic() # Claude API
│       ├── call_openai()   # OpenAI API
│       └── retry_backoff() # Error handling
│
└── tests/
    ├── test_router_agent.py
    ├── test_embeddings.py
    ├── test_retrieval.py
    └── fixtures/
        └── sample_episodes.json
```

## Documentation (`docs/`)

```
docs/
├── ARCHITECTURE.md         # Full v1 technical design
├── PROJECT_STRUCTURE.md    # This file
├── DEVELOPMENT_PLAN.md     # Implementation roadmap
└── EXAMPLE.md              # Process walkthrough (optional)
```

## Runtime Directories

```
~/.sqrl/                    # Global user data
├── config.toml             # User settings
│   ├── [user]
│   │   └── id = "alice"
│   ├── [llm]
│   │   └── anthropic_api_key = "sk-ant-..."
│   └── [daemon]
│       └── socket_path = "/tmp/sqrl_router.sock"
│
├── squirrel.db             # Global SQLite (user_style memories)
│   └── Tables: memories (user_style only)
│
├── projects.json           # Registered repos
│   └── ["/home/user/project1", "/home/user/project2"]
│
└── logs/                   # Daemon logs
    └── daemon.log

<repo>/.sqrl/               # Per-project data
├── squirrel.db             # Project SQLite
│   └── Tables:
│       ├── memories        # project_fact, pitfall, recipe
│       ├── events          # Raw log events
│       └── episodes        # Grouped sessions
│
└── config.toml             # Project overrides (optional)
```

## IPC Protocol

```
Transport: Unix domain socket
Path: /tmp/sqrl_router.sock (Linux/macOS)
      \\.\pipe\sqrl_router (Windows)

Protocol: JSON-RPC style

Request:
{
  "method": "router_agent" | "fetch_memories",
  "params": { ... },
  "id": 123
}

Response:
{
  "result": { ... },
  "id": 123
}

Methods:
1. router_agent
   params.mode: "ingest" | "route"
   params.payload: mode-specific data

2. fetch_memories
   params.repo: string
   params.task: string (optional)
   params.memory_types: ["user_style", "project_fact", ...]
   params.max_results: int
```

## File Responsibilities

### Rust Daemon

| File | Responsibility | Key APIs |
|------|---------------|----------|
| `daemon.rs` | Process lifecycle | start(), stop(), batch_loop() |
| `watcher.rs` | Log file watching | LogWatcher, parse_line() |
| `events.rs` | Event/Episode models | Event, Episode, group_episodes() |
| `storage.rs` | SQLite + sqlite-vec | save_memory(), query_memories() |
| `ipc.rs` | IPC to Python | router_agent(), fetch_memories() |
| `mcp.rs` | MCP server (2 tools) | squirrel_get_task_context(), squirrel_search_memory() |
| `cli.rs` | CLI commands | cmd_init(), cmd_daemon(), cmd_mcp() |
| `config.rs` | Settings | load_config(), save_config() |

### Python Memory Service

| File | Responsibility | Key APIs |
|------|---------------|----------|
| `server.py` | IPC server | start_server(), handle_request() |
| `router_agent.py` | Dual-mode router | ingest_mode(), route_mode() |
| `embeddings.py` | ONNX embeddings | embed(), batch_embed() |
| `retrieval.py` | Memory search | retrieve_candidates(), generate_why() |
| `llm.py` | LLM calls | call_anthropic(), call_openai() |

## SQLite Schema

```sql
-- memories table (both global and project DBs)
CREATE TABLE memories (
  id TEXT PRIMARY KEY,
  content_hash TEXT NOT NULL UNIQUE,
  content TEXT NOT NULL,
  memory_type TEXT NOT NULL,  -- user_style | project_fact | pitfall | recipe
  repo TEXT NOT NULL,
  embedding BLOB,             -- 384-dim float32 vector
  confidence REAL NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- events table (project DB only)
CREATE TABLE events (
  id TEXT PRIMARY KEY,
  cli TEXT NOT NULL,          -- claude_code | codex | cursor | gemini
  repo TEXT NOT NULL,
  event_type TEXT NOT NULL,   -- user_message | assistant_response | tool_use
  content TEXT NOT NULL,
  file_paths TEXT,            -- JSON array
  timestamp TEXT NOT NULL,
  processed INTEGER DEFAULT 0
);

-- episodes table (project DB only)
CREATE TABLE episodes (
  id TEXT PRIMARY KEY,
  repo TEXT NOT NULL,
  cli TEXT NOT NULL,
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  event_ids TEXT NOT NULL,    -- JSON array
  processed INTEGER DEFAULT 0
);
```

## Development Workflow

```bash
# 1. Clone repo
git clone https://github.com/kaminoguo/Squirrel.git
cd Squirrel

# 2. Build Rust daemon
cd agent
cargo build

# 3. Install Python service
cd ../memory_service
pip install -e .

# 4. Start daemon
cd ../agent
cargo run -- daemon start

# 5. Initialize a project
cd ~/my-project
sqrl init

# 6. Configure Claude Code MCP
# Add to ~/.claude/mcp.json:
# "squirrel": {"command": "sqrl", "args": ["mcp"]}

# 7. Start coding - Squirrel learns automatically
```

## Build Artifacts

```
agent/target/
├── debug/sqrl              # Development binary
└── release/sqrl            # Production binary

memory_service/
└── models/all-MiniLM-L6-v2.onnx  # Downloaded on first run
```

## Notes for AI Assistants

When modifying code:
- Rust changes: `agent/src/<file>.rs`
- Python changes: `memory_service/squirrel_memory/<file>.py`
- Docs updates: `docs/<file>.md`

Key integration points:
- IPC protocol: `agent/src/ipc.rs` ↔ `memory_service/squirrel_memory/server.py`
- SQLite schema: `agent/src/storage.rs`
- MCP tools: `agent/src/mcp.rs`
- Router Agent prompts: `memory_service/squirrel_memory/router_agent.py`
