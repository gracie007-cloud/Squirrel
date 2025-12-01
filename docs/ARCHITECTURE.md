# Squirrel Architecture (v1)

## Goal

Squirrel is a local-first "memory OS" for developers.

- Watches real development activity (Claude Code, Codex, Gemini CLI, Cursor logs)
- Extracts structured, long-term memory (user_style, project_fact, pitfall, recipe)
- Exposes memory to LLMs via MCP server that works across tools

**Tech stack:**
- **Rust** – daemon, log watchers, SQLite, MCP server, CLI, Context Formatter
- **Python** – Router Agent (INGEST + ROUTE modes), embeddings, retrieval

---

## High-Level Architecture (v1)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                     │
│                         (Passive Log Watching)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Claude Code          Gemini CLI           Codex              Cursor        │
│       │                    │                  │                   │          │
│       ▼                    ▼                  ▼                   ▼          │
│   transcript           ~/.gemini/           ~/.codex/         ~/.cursor/     │
│   files                logs                 logs              logs           │
│       │                    │                  │                   │          │
│       └────────────────────┴──────────────────┴───────────────────┘          │
│                                    │                                         │
│                                    ▼                                         │
│                        ┌─────────────────────┐                               │
│                        │   Rust Daemon       │                               │
│                        │   (File Watcher)    │                               │
│                        │                     │                               │
│                        │   • Watch log files │                               │
│                        │   • Parse events    │                               │
│                        │   • Group episodes  │                               │
│                        └─────────────────────┘                               │
│                                    │                                         │
│                      New events / episodes detected                          │
│                                    │                                         │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            EXTRACT LAYER                                     │
│                     (Python Memory Service)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Rust daemon sends episode via IPC (Unix socket)                            │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │              Router Agent (INGEST mode)                              │   │
│   │                                                                      │   │
│   │   Input:                                                             │   │
│   │     {                                                                │   │
│   │       "mode": "INGEST",                                              │   │
│   │       "cli": "claude_code",                                          │   │
│   │       "repo": "/path/to/repo",                                       │   │
│   │       "episode_text": "raw conversation / episode text"              │   │
│   │     }                                                                │   │
│   │                                                                      │   │
│   │   Output:                                                            │   │
│   │     {                                                                │   │
│   │       "operations": [                                                │   │
│   │         {                                                            │   │
│   │           "operation": "ADD" | "UPDATE" | "DELETE" | "NONE",         │   │
│   │           "memory_type": "user_style" | "project_fact" |             │   │
│   │                          "pitfall" | "recipe",                       │   │
│   │           "content": "extracted memory text",                        │   │
│   │           "confidence": 0.0-1.0                                      │   │
│   │         }                                                            │   │
│   │       ]                                                              │   │
│   │     }                                                                │   │
│   │                                                                      │   │
│   │   Gate: Only apply ADD/UPDATE when confidence >= 0.7                 │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         Embedding (ONNX)                             │   │
│   │                      all-MiniLM-L6-v2 (384-dim)                      │   │
│   │                      ~25MB, ~10ms inference                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         SQLite + sqlite-vec                          │   │
│   │                                                                      │   │
│   │   memories table:                                                    │   │
│   │   ├─ content_hash    (SHA-256, dedup key)                            │   │
│   │   ├─ content         (memory text)                                   │   │
│   │   ├─ memory_type     (user_style | project_fact | pitfall | recipe)  │   │
│   │   ├─ repo            (project affinity filter)                       │   │
│   │   ├─ embedding       (384-dim vector)                                │   │
│   │   ├─ confidence      (0.0-1.0, from INGEST)                          │   │
│   │   ├─ created_at                                                      │   │
│   │   └─ updated_at                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                             OUTPUT LAYER                                     │
│                          (MCP-first, v1)                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   CLI calls MCP tool → Rust MCP Server → Python Router Agent (ROUTE)        │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │              Router Agent (ROUTE mode)                               │   │
│   │                                                                      │   │
│   │   Input:                                                             │   │
│   │     {                                                                │   │
│   │       "mode": "ROUTE",                                               │   │
│   │       "cli": "claude_code",                                          │   │
│   │       "repo": "/path/to/repo",                                       │   │
│   │       "task": "user's current task description",                     │   │
│   │       "path_hint": "optional/path/hint",                             │   │
│   │       "context_budget_tokens": 800                                   │   │
│   │     }                                                                │   │
│   │                                                                      │   │
│   │   Output:                                                            │   │
│   │     {                                                                │   │
│   │       "need_memory": true,                                           │   │
│   │       "memory_types": ["project_fact", "pitfall"],                   │   │
│   │       "effective_budget_tokens": 600                                 │   │
│   │     }                                                                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │              Python Retrieval (fetch_memories)                       │   │
│   │                                                                      │   │
│   │   Input:                                                             │   │
│   │     {                                                                │   │
│   │       "repo": "/path/to/repo",                                       │   │
│   │       "memory_types": ["project_fact", "pitfall"],                   │   │
│   │       "task": "current task for embedding",                          │   │
│   │       "path_hint": "optional/path",                                  │   │
│   │       "budget_tokens": 600                                           │   │
│   │     }                                                                │   │
│   │                                                                      │   │
│   │   Process:                                                           │   │
│   │     1. Embed task → query vector                                     │   │
│   │     2. sqlite-vec similarity search                                  │   │
│   │     3. Filter by repo (project affinity)                             │   │
│   │     4. Rank by: similarity × confidence × recency                    │   │
│   │     5. Truncate to budget_tokens                                     │   │
│   │     6. Generate "why" for each memory (heuristic templates)          │   │
│   │                                                                      │   │
│   │   Output:                                                            │   │
│   │     [                                                                │   │
│   │       {                                                              │   │
│   │         "memory_type": "project_fact",                               │   │
│   │         "content": "Auth uses JWT with RS256",                       │   │
│   │         "score": 0.87,                                               │   │
│   │         "why": "Relevant because it describes auth pattern"          │   │
│   │       },                                                             │   │
│   │       ...                                                            │   │
│   │     ]                                                                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │              Context Formatter (Rust)                                │   │
│   │                                                                      │   │
│   │   Input: memories with "why" + task + budget                         │   │
│   │                                                                      │   │
│   │   Output (MCP response):                                             │   │
│   │     Relevant context for your task:                                  │   │
│   │     - [project_fact] Auth uses JWT with RS256                        │   │
│   │       (Relevant because it describes auth pattern)                   │   │
│   │     - [pitfall] Don't use jwt.sign() for verification                │   │
│   │       (Relevant because similar bug happened before)                 │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      MCP Channel (v1)                                │   │
│   │                                                                      │   │
│   │   Tools:                                                             │   │
│   │   ├─ squirrel_get_task_context                                       │   │
│   │   │    Automatic, Router decides what's relevant                     │   │
│   │   │    Uses ROUTE mode → retrieval → formatted response              │   │
│   │   │                                                                  │   │
│   │   └─ squirrel_search_memory                                          │   │
│   │        Explicit user query, direct semantic search                   │   │
│   │        Bypasses Router, respects budget_tokens only                  │   │
│   │                                                                      │   │
│   │   Note: Hook/File channels reserved for v2 (auto-injection)          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

| Component | Language | Responsibilities |
|-----------|----------|------------------|
| **Rust Daemon** | Rust | Log watching, event parsing, episode grouping, SQLite ownership, MCP server, Context Formatter, IPC client |
| **Python Memory Service** | Python | Router Agent (INGEST + ROUTE), embeddings (ONNX), retrieval (sqlite-vec), "why" generation |

---

## IPC Protocol

```
Transport: Unix domain socket (/tmp/sqrl_router.sock)
           Windows: Named pipe (\\.\pipe\sqrl_router)

Protocol: JSON-RPC style request/response

Request:
{
  "method": "router_agent" | "fetch_memories",
  "params": { ... payload ... },
  "id": 123
}

Response:
{
  "result": { ... },
  "id": 123
}
```

---

## Data Definitions

### Event (smallest unit)
```json
{
  "type": "user_prompt" | "assistant_response" | "file_edit" | "tool_call",
  "cli": "claude_code" | "codex" | "cursor" | "gemini",
  "repo": "/path/to/repo",
  "timestamp": "2025-01-15T10:30:00Z",
  "content": "raw content"
}
```

### Episode (grouped events)
```json
{
  "cli": "claude_code",
  "repo": "/path/to/repo",
  "start_time": "2025-01-15T10:30:00Z",
  "end_time": "2025-01-15T10:45:00Z",
  "events": [ ... ],
  "episode_text": "concatenated/summarized text for Router Agent"
}
```

Grouping criteria: Same repo + same CLI + inactivity gap < N minutes

---

## Data Flow (v1)

```
1. INPUT (Passive, logs only)
   ├─ User works in Claude Code / Codex / Cursor / Gemini
   ├─ Each CLI writes to its log location
   ├─ Rust Daemon watches logs → parses events
   └─ Rust groups events into episodes → stores raw in SQLite

2. EXTRACT (Router Agent – INGEST mode)
   ├─ Rust sends episode to Python via IPC
   ├─ Router Agent (INGEST) returns operations
   ├─ Python applies ADD/UPDATE/DELETE to memories table
   │   (only if confidence >= 0.7)
   └─ Python generates embeddings, stores in sqlite-vec

3. OUTPUT (MCP-first, Router Agent – ROUTE mode)
   ├─ CLI calls MCP tool: squirrel_get_task_context
   ├─ Rust MCP handler builds ROUTE payload
   ├─ Python Router Agent (ROUTE) returns need_memory + memory_types + budget
   ├─ Python fetch_memories() does:
   │   └─ embed query → sqlite-vec search → rank → truncate → add "why"
   ├─ Rust Context Formatter assembles final text
   └─ MCP response returned to CLI

4. Future (v2)
   ├─ Hook channel: Auto-inject via SessionStart/BeforeAgent
   └─ File channel: Update CLAUDE.md / AGENTS.md / .cursorrules
```

---

## Memory Types (4 Only)

| Type | Purpose | "Why" Template |
|------|---------|----------------|
| `user_style` | User preferences | "Matches your coding style preferences" |
| `project_fact` | Architecture/decisions | "Describes existing pattern in this repo" |
| `pitfall` | Bugs, things that failed | "Similar issue encountered before" |
| `recipe` | Solutions that worked | "Pattern you successfully used before" |

---

## MCP Tools (v1)

### squirrel_get_task_context (Primary)

Task-aware memory retrieval with relevance explanations.

**Input:**
```json
{
  "project_root": "/path/to/repo",
  "task_description": "Add a delete endpoint for inventory",
  "path_hint": "src/routes/inventory.py",
  "context_budget_tokens": 600
}
```

**Output:**
```
Relevant context for your task:
- [project_fact] Auth uses JWT with RS256
  (Relevant because it describes auth pattern)
- [user_style] Prefers async/await for handlers
  (Matches your coding style preferences)
```

### squirrel_search_memory (Explicit)

Direct semantic search, bypasses Router.

**Input:**
```json
{
  "project_root": "/path/to/repo",
  "query": "JWT authentication",
  "top_k": 5
}
```

**Output:**
```json
{
  "results": [
    {
      "memory_type": "project_fact",
      "content": "Auth uses JWT with RS256",
      "score": 0.92,
      "why": "Directly mentions JWT authentication"
    }
  ]
}
```

---

## Key Design Decisions (v1)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Input method | Logs only, no hooks | Passive learning, works across all CLIs |
| Output method | MCP only | Simplest integration, hooks/files in v2 |
| Router location | Python | LLM libraries, embeddings easier |
| MCP server | Rust | Already runs daemon, owns SQLite |
| IPC | Unix socket | Fast, no HTTP overhead, local only |
| Confidence threshold | 0.7 | Filter low-quality extractions |
| "Why" generation | Python heuristics | Avoid extra LLM calls |

---

## Directory Layout

### Global (`~/.sqrl/`)

```
~/.sqrl/
├── config.toml          # user_id, API keys, defaults
├── user.db              # global user_style memory
├── projects.json        # registered projects
├── daemon.json          # daemon PID + port
└── memory-service.json  # Python service PID + socket path
```

### Per Project (`<repo>/.ctx/`)

```
<repo>/.ctx/
├── data.db              # events, episodes, memories
└── views/               # cached views (future)
```

---

## SQLite Schema (v1)

### memories table

```sql
CREATE TABLE memories (
  id TEXT PRIMARY KEY,
  content_hash TEXT NOT NULL UNIQUE,  -- SHA-256, dedup
  content TEXT NOT NULL,
  memory_type TEXT NOT NULL,          -- user_style|project_fact|pitfall|recipe
  repo TEXT NOT NULL,                 -- project affinity
  embedding BLOB,                     -- 384-dim float32
  confidence REAL NOT NULL,           -- 0.0-1.0
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_memories_repo_type ON memories(repo, memory_type);
CREATE INDEX idx_memories_updated ON memories(updated_at);
```

### events table

```sql
CREATE TABLE events (
  id TEXT PRIMARY KEY,
  cli TEXT NOT NULL,
  repo TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  event_type TEXT NOT NULL,
  content TEXT NOT NULL,
  hash TEXT NOT NULL UNIQUE,
  processed_at TEXT
);
```

### episodes table

```sql
CREATE TABLE episodes (
  id TEXT PRIMARY KEY,
  cli TEXT NOT NULL,
  repo TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  event_ids TEXT NOT NULL,  -- JSON array
  episode_text TEXT NOT NULL,
  processed_at TEXT
);
```
