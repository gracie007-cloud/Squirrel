# Squirrel – Engineering Memory OS (Final Architecture Spec)

## Goal

Squirrel is a local-first "memory OS" for developers.

- It watches real development activity (Claude Code logs, later Codex/Gemini CLI, Cursor, git, CI...)
- It turns that activity into structured, long-term memory (user style + project facts + pitfalls + recipes)
- It exposes that memory to LLMs via a single MCP server (`ctx-memory`) that works across tools.

**Tech stack:**
- **Rust** – local agent: daemon, watchers, SQLite, MCP server, CLI
- **Python** – memory engine: event → episode → memory items → views

---

## 1. High-level Components

### 1.1 Rust Agent (one per machine)

Binary: `sqrl` (or `ctx`).

**Responsibilities:**

- **Global daemon** (one per machine)
  - Manages project watchers
  - Manages local SQLite DBs
  - Spawns and supervises the Python memory service
  - Exposes a local TCP API to MCP and CLI

- **Watchers**
  - Phase 1: watch Claude Code JSONL logs under `~/.claude/projects/...`
  - Later: Codex CLI, Gemini CLI, Cursor, git logs, CI logs
  - Normalize all into `Event` structs

- **Storage**
  - Per-project SQLite at `<repo>/.ctx/data.db`
  - Global user memory at `~/.sqrl/user.db`

- **MCP server**
  - `sqrl mcp` – short-lived stdio MCP process for Claude Code / other hosts
  - Connects to daemon over local TCP

- **CLI**
  - `sqrl init` – initialize `.ctx/` for a repo and register it
  - `sqrl config` – set user_id, API keys, defaults
  - `sqrl daemon` – start/stop/status for daemon (daemon also auto-starts as needed)
  - `sqrl status` – inspect project memory state

### 1.2 Python Memory Service

Package: `squirrel_memory`

**Process:**
- HTTP server on `localhost:<port>` (port recorded in `~/.sqrl/memory-service.json`)

**Endpoints:**
- `POST /process_events`
- `GET /views/user_style`
- `GET /views/project_brief`
- `GET /views/pitfalls`
- `GET /search_memory`

**Responsibilities:**
- Group raw events into episodes
- Extract structured `MemoryItems` from episodes (user_style, project_fact, pitfalls, recipes...)
- Apply Mem0-style update logic (ADD/UPDATE/NOOP/DELETE) to keep memory clean and up-to-date
- Generate compact views for LLM consumption
- Perform memory search / RAG for deeper queries

---

## 2. Directory Layout & Storage

### 2.1 Global (`~/.sqrl`)

```
~/.sqrl/
  config.toml          # user_id, API keys, default model, etc.
  user.db              # global user_style memory
  projects.json        # {"projects": ["/abs/path/to/repo1", ...]}
  daemon.json          # {"pid": ..., "host": "127.0.0.1", "port": 9468}
  memory-service.json  # {"pid": ..., "host": "127.0.0.1", "port": 8734}
```

### 2.2 Per project (`<repo>/.ctx`)

```
<repo>/.ctx/
  data.db              # SQLite: events, episodes, memory_items, view_meta
  views/
    user_style.json
    project_brief.json
    pitfalls.json
    .meta.json         # optional debug mirror of view_meta
```

**Rule:** `project_id` is always the absolute path, e.g. `"/Users/alice/projects/inventory-api"`.

---

## 3. Data Model (SQLite schema)

### 3.1 Events (raw activity)

Table: `events` in `<repo>/.ctx/data.db`

```sql
CREATE TABLE events (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  source_tool TEXT NOT NULL,          -- 'claude_code' | 'cursor' | 'codex' | 'gemini_cli' | 'git' | ...
  session_id TEXT,                    -- tool session / conversation id
  timestamp TEXT NOT NULL,            -- ISO8601

  event_type TEXT NOT NULL,           -- 'user_message' | 'assistant_response' | 'code_change' | 'test_run' | ...
  content_json TEXT NOT NULL,         -- raw log JSON serialized

  file_paths TEXT NOT NULL,           -- JSON array: ["src/auth.py", ...]
  hash TEXT NOT NULL,                 -- dedup hash
  processed_at TEXT NULL              -- when sent to /process_events (NULL = not yet)
);

CREATE INDEX idx_events_project_time ON events(project_id, timestamp);
CREATE INDEX idx_events_processed   ON events(project_id, processed_at);
CREATE INDEX idx_events_session     ON events(project_id, session_id);
```

**Deduplication rule:**

Build a canonical struct with:
- `project_id`
- `source_tool`
- `event_type`
- `session_id` (if present)
- `timestamp_bucket` = timestamp rounded to 5 minutes
- sorted `file_paths`
- `content_signature` (lightly normalized content)

`hash = sha256(JSON(canonical_struct))`

If a row exists with same `(project_id, hash)`, drop the new event.

### 3.2 Episodes (semantic sessions)

Table: `episodes` in `<repo>/.ctx/data.db`

```sql
CREATE TABLE episodes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  session_id TEXT,           -- main session id, if any
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  event_count INTEGER NOT NULL,
  summary TEXT NOT NULL,     -- short LLM summary (80-150 tokens)
  importance REAL NOT NULL,  -- 0.0-1.0
  created_at TEXT NOT NULL
);

CREATE INDEX idx_episodes_project_time ON episodes(project_id, start_ts);
```

**Segmentation logic (Nemori-style):**
- Group by `(project_id, user_id)`, sort by timestamp
- Primary segmentation by `session_id`
- Within a session:
  - New episode if time gap > 20 minutes OR (optional) topic change (LLM)
- Keep episodes with at least 3 events; otherwise merge with neighbors.

### 3.3 MemoryItems (long-term facts/preferences)

Table: `memory_items` in `<repo>/.ctx/data.db`

```sql
CREATE TABLE memory_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  user_id TEXT,                   -- NULL = project-wide memory
  scope TEXT NOT NULL,            -- 'user' | 'project'

  type TEXT NOT NULL,             -- 'user_style' | 'project_fact' | 'pitfall' | 'recipe'
  key TEXT NOT NULL,              -- logical key, e.g. 'async_preference', 'framework', 'endpoint:/login'
  content TEXT NOT NULL,          -- human-readable statement
  tags TEXT NOT NULL,             -- JSON array, e.g. ["python","async","testing"]

  importance REAL NOT NULL,       -- 0.0-1.0
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,

  source_episode_id TEXT,
  source_event_ids TEXT NOT NULL, -- JSON array: ["evt_1","evt_2",...]

  embedding BLOB,                 -- optional: vector embedding
  graph_neighbors TEXT,           -- JSON array of related memory ids
  deleted INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_mem_project_type ON memory_items(project_id, type);
CREATE INDEX idx_mem_key          ON memory_items(project_id, key);
CREATE INDEX idx_mem_updated      ON memory_items(project_id, updated_at);
```

**Key invariants:**
- `(project_id, type, key, user_id/scope)` is the anchor for Mem0-style updates.
- `embedding` and `graph_neighbors` are future extensions; schema is defined now but can be left NULL initially.

### 3.4 Global user memory (`~/.sqrl/user.db`)

Table: `user_style_items`

```sql
CREATE TABLE user_style_items (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  key TEXT NOT NULL,
  content TEXT NOT NULL,
  tags TEXT NOT NULL,          -- JSON array
  importance REAL NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  source TEXT NOT NULL         -- 'llm' | 'manual'
);

CREATE UNIQUE INDEX idx_user_style_key ON user_style_items(user_id, key);
```

### 3.5 View meta (staleness)

Table: `view_meta` in `<repo>/.ctx/data.db`

```sql
CREATE TABLE view_meta (
  view_name TEXT PRIMARY KEY,       -- 'user_style' | 'project_brief' | 'pitfalls'
  last_generated TEXT NOT NULL,
  events_count_at_gen INTEGER NOT NULL,
  ttl_seconds INTEGER NOT NULL
);
```

`views/*.json` contain the actual view JSON; `view_meta` is the authoritative staleness source.

---

## 4. Rust Runtime Behavior

### 4.1 `sqrl init`

1. Ensure `~/.sqrl/` exists; bootstrap `config.toml`, `user.db`, `projects.json` if needed
2. In current repo:
   - Create `<repo>/.ctx/`
   - Initialize `data.db` with required tables
   - Add the project's absolute path to `projects.json`
3. Optionally detect Claude Code MCP config and (with confirmation) add `ctx-memory` server entry

### 4.2 Daemon

One global daemon per machine:

1. Reads `~/.sqrl/projects.json` to know which repos to watch
2. For each project:
   - Ensures `<repo>/.ctx/data.db` exists with correct schema
   - Spawns/maintains a watcher
3. Spawns/maintains Python memory service:
   - E.g. `python -m squirrel_memory.server --port <random>`
   - Records port + PID in `memory-service.json`
4. Listens on local TCP (`127.0.0.1:<port>`, stored in `daemon.json`) for:
   - CLI requests
   - MCP requests (via `sqrl mcp`)
5. Event batching → Python:
   - Periodically (e.g. every 30s) or when ≥20 unsent events:
     - Query `events WHERE processed_at IS NULL ORDER BY timestamp LIMIT 200`
     - Build `ProcessEventsRequest`
     - Call `POST /process_events` on Python service
     - On success: set `processed_at = now()` for those events
     - On failure: log and retry later with backoff

### 4.3 MCP server (`sqrl mcp`)

Implements latest MCP Tools spec over stdio.

On startup:
1. Reads `daemon.json` to find daemon host/port
2. If daemon not found, starts it and waits briefly

**Tools:**
- `get_user_style_view`
- `get_project_brief_view`
- `get_pitfalls_view`
- `search_project_memory`

Each tool:
1. Translates MCP input → internal request (`project_root`, `query`, etc.)
2. Calls daemon over local TCP
3. Daemon calls Python views/search and returns JSON
4. MCP layer wraps JSON into structured tool output (with declared JSON Schema)

---

## 5. Python Memory Service Behavior

### 5.1 `POST /process_events`

**Request:**
```json
{
  "project_id": "/abs/path/to/repo",
  "user_id": "alice",
  "events": [ /* EventDTOs corresponding to events table */ ]
}
```

**Processing:**

1. **Episode grouping**
   - Group by `(project_id, user_id, session_id)`
   - Within each group, split on time gap > 20min (and optionally on topic breaks)
   - For each episode:
     - Compute summary (short LLM call)
     - Compute importance (simple heuristic + optional LLM score)
     - Insert into `episodes` table

2. **Memory extraction**
   - For each episode:
     - Build a compact text context from events (messages, diffs, test runs)
     - Call LLM with an extraction prompt to produce candidate MemoryItems:
       - `user_style` (coding style, testing habits, tool preferences...)
       - `project_fact` (framework, DB, services, important endpoints...)
       - Later: pitfalls, recipes
     - Each candidate: `{type, key, content, tags, importance, source_episode_id, source_event_ids}`

3. **Mem0-style updates**
   - For each new candidate item:
     - Query existing `memory_items` with same `(project_id, type, key, scope, user_id)` (or `user_style_items` for global)
     - If none: ADD new row
     - If exists:
       - Ask LLM to decide: `ADD_NEW`, `UPDATE_EXISTING`, `NOOP`, `DELETE_AND_ADD`
       - Apply:
         - `ADD_NEW` → keep old, insert new
         - `UPDATE_EXISTING` → merge content, update existing row
         - `NOOP` → skip
         - `DELETE_AND_ADD` → mark old as deleted, insert new row

**Return:**
```json
{
  "episode_ids": ["ep_...", ...],
  "memory_item_ids": ["mem_...", ...]
}
```

### 5.2 `GET /views/user_style`

**Query params:** `project_id`, `user_id` (optional)

**Algorithm:**
1. Read `view_meta WHERE view_name='user_style'`
2. Count total events for project
3. If not stale:
   - Return cached JSON from `views/user_style.json`
4. If stale:
   - Query `memory_items` where:
     - `project_id = ?`
     - `type = 'user_style'`
     - `scope IN ('user','project')`
   - Query global `user_style_items` from `~/.sqrl/user.db`
   - Merge project-specific + global styles (project overrides refine global)
   - Sort by importance & recency; keep top N (e.g. 20)
   - Call LLM with a view prompt to generate:
     - `items`: normalized `{key, summary, tags, importance}`
     - `markdown`: short, well-structured summary
   - Write JSON to `views/user_style.json`
   - Update `view_meta` with new timestamp, `events_count_at_gen`

**Stale rules (v1):**
- `ttl_seconds = 3600` (1 hour)
- OR `events_count - events_count_at_gen >= 200`

**Return type:** `UserStyleView` JSON:
```json
{
  "type": "user_style_view",
  "project_id": "/abs/path",
  "user_id": "alice",
  "generated_at": "2025-11-25T10:20:00Z",
  "token_estimate": 180,
  "items": [
    {
      "key": "async_preference",
      "summary": "Prefers async/await for all I/O-bound handlers.",
      "tags": ["python", "async"],
      "importance": 0.9
    }
  ],
  "markdown": "## User Coding Style\n\n- Always use async/await..."
}
```

### 5.3 `GET /views/project_brief`

**Similar pattern:**

- Inputs: `project_id`
- Stale rules:
  - `ttl_seconds = 600` (10 min)
  - or events_count delta >= 100
- Data sources:
  - `memory_items` with `type='project_fact'`
  - Optionally: some episodes for context

**Output:** `ProjectBriefView` JSON:
```json
{
  "type": "project_brief_view",
  "project_id": "/abs/path",
  "generated_at": "...",
  "token_estimate": 200,
  "modules": [
    {
      "name": "API Layer",
      "paths": ["routes/*.py"],
      "summary": "FastAPI endpoints for inventory and auth."
    }
  ],
  "key_facts": [
    "Framework: FastAPI",
    "Database: PostgreSQL with async SQLAlchemy",
    "Auth: JWT tokens via /login endpoint"
  ],
  "markdown": "## Project Overview\n\n- Framework: FastAPI\n- ..."
}
```

### 5.4 `GET /views/pitfalls`

**Inputs:**
- `project_id`
- optional `scope_paths[]`
- optional `task_description`

**Stale rules:**
- `ttl_seconds = 600`
- or events_count delta >= 50

**Data:**
- `memory_items` with `type='pitfall'` and tags/file_paths intersecting `scope_paths`

**Output:** `PitfallsView` JSON with `items[]` + `markdown`.

### 5.5 `GET /search_memory`

**Inputs:**
- `project_id`
- `query` (string)
- optional `top_k` (default 5)
- optional `types[]` (filter by memory type)
- optional `scope_paths[]` (to bias scoring)

**Behavior:**
1. Filter `memory_items` by project + types
2. Score:
   - If embeddings available:
     - `score = α * cos_sim(query_emb, item_emb) + β * importance + γ * recency`
   - Else:
     - fallback to simple keyword / BM25 style scoring + importance + recency
3. Optionally run a small reranker LLM over top-K candidates

**Return:**
```json
{
  "results": [
    {
      "memory_id": "mem_123",
      "type": "project_fact",
      "key": "auth_mechanism",
      "content": "Auth uses JWT tokens via /login endpoint.",
      "tags": ["auth","jwt","endpoint"],
      "importance": 0.9
    }
  ]
}
```

---

## 6. MCP Tools (northbound contract)

We target the latest MCP spec (mid-2025) with structured tool outputs.

Squirrel's MCP server (`sqrl mcp`) exposes 4 tools:

### `get_user_style_view`

**Input:**
```json
{ "project_root": "/abs/path/to/repo", "user_id": "alice" }
```

**Output:** JSON matching `UserStyleView` schema

### `get_project_brief_view`

**Input:**
```json
{ "project_root": "/abs/path/to/repo" }
```

**Output:** JSON `ProjectBriefView`

### `get_pitfalls_view`

**Input:**
```json
{
  "project_root": "/abs/path/to/repo",
  "scope_paths": ["src/auth.py"],
  "task_description": "Refactor auth flow"
}
```

**Output:** JSON `PitfallsView`

### `search_project_memory`

**Input:**
```json
{
  "project_root": "/abs/path/to/repo",
  "query": "JWT login tests",
  "top_k": 5,
  "types": ["project_fact","pitfall"],
  "scope_paths": ["src/auth.py"]
}
```

**Output:**
```json
{
  "results": [
    {
      "memory_id": "mem_123",
      "type": "project_fact",
      "key": "auth_mechanism",
      "content": "Auth uses JWT tokens via /login endpoint.",
      "tags": ["auth","jwt","endpoint"],
      "importance": 0.9
    }
  ]
}
```

---

## Design Notes

The MCP layer is deliberately thin:
- It doesn't do memory logic
- It just:
  1. Maps tool args → internal request
  2. Calls daemon over local TCP
  3. Returns the JSON view or search results
