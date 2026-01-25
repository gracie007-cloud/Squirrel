# Squirrel Interfaces

All IPC, MCP, and CLI contracts.

## IPC Protocol

Unix socket at `/tmp/sqrl.sock`. JSON-RPC 2.0 format.

### Request Format

```json
{
    "jsonrpc": "2.0",
    "method": "<method_name>",
    "params": { ... },
    "id": <integer>
}
```

### Response Format

```json
{
    "jsonrpc": "2.0",
    "result": { ... },
    "id": <integer>
}
```

### Error Format

```json
{
    "jsonrpc": "2.0",
    "error": {
        "code": <integer>,
        "message": "<string>"
    },
    "id": <integer>
}
```

---

## IPC Methods

### IPC-001: process_episode

Daemon → Memory Service. Process episode events, extract memories.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "process_episode",
  "params": {
    "project_id": "payment-api",
    "project_root": "/home/alice/projects/payment-api",
    "events": [
      {
        "ts": "2024-12-10T10:00:00Z",
        "role": "user",
        "content_summary": "asked to call Stripe API"
      },
      {
        "ts": "2024-12-10T10:01:00Z",
        "role": "assistant",
        "content_summary": "ran python script with requests library"
      },
      {
        "ts": "2024-12-10T10:01:30Z",
        "role": "tool_error",
        "content_summary": "SSLError: certificate verify failed"
      }
    ],
    "existing_user_styles": [
      {
        "id": "style-1",
        "text": "Prefer async/await over callbacks"
      },
      {
        "id": "style-2",
        "text": "Never use emoji"
      }
    ],
    "existing_project_memories": [
      {
        "id": "mem-1",
        "category": "backend",
        "subcategory": "main",
        "text": "Use httpx as HTTP client"
      }
    ]
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "skipped": false,
    "skip_reason": null,
    "user_styles": [
      {
        "op": "ADD",
        "text": "Prefers explicit error messages over generic ones"
      }
    ],
    "project_memories": [
      {
        "op": "ADD",
        "category": "backend",
        "subcategory": "main",
        "text": "requests library has SSL issues; use httpx instead"
      },
      {
        "op": "UPDATE",
        "target_id": "mem-1",
        "new_text": "Use httpx as HTTP client. requests causes SSL errors."
      }
    ]
  },
  "id": 1
}
```

**Operations:**

| Op | Action |
|----|--------|
| ADD | Insert new memory |
| UPDATE | Merge with existing memory |
| DELETE | Remove outdated memory |

**Model Pipeline:**
1. Log Cleaner (gemini-3.0-flash) - compress, decide if worth processing
2. Memory Extractor (gemini-3.0-flash) - extract user styles + project memories

---

### IPC-002: sync_user_style

Memory Service → Daemon. Sync user style to agent.md files.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "sync_user_style",
  "params": {
    "styles": [
      "Prefer async/await over callbacks",
      "Never use emoji",
      "Commits should use minimal English"
    ],
    "target_files": [
      "~/.claude/CLAUDE.md",
      "~/.cursor/rules/personal.mdc"
    ]
  },
  "id": 3
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "synced_files": [
      "~/.claude/CLAUDE.md",
      "~/.cursor/rules/personal.mdc"
    ]
  },
  "id": 3
}
```

---

## MCP Tools

### MCP-001: squirrel_get_memory

Get all project memories, grouped by category.

**Tool Definition:**
```json
{
  "name": "squirrel_get_memory",
  "description": "Get project memories from Squirrel. Call when user asks to 'use Squirrel' or wants project context.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_root": {
        "type": "string",
        "description": "Absolute path to project root"
      }
    },
    "required": ["project_root"]
  }
}
```

**Response Format:**
```markdown
## frontend
- Component library uses shadcn/ui
- State management with Zustand

## backend
- Use httpx as HTTP client
- API uses FastAPI with Pydantic models

## docs_test
- Tests use pytest with fixtures in conftest.py

## other
- Deploy via GitHub Actions to Vercel
```

Memories ordered by use_count within each category.

---

## CLI Commands

### CLI-001: sqrl

Show help.

**Usage:** `sqrl`

**Action:** Displays available commands and usage information.

---

### CLI-002: sqrl init

Initialize project for Squirrel.

**Usage:**
```bash
sqrl init                    # Initialize + process last 30 days of history
sqrl init --no-history       # Initialize without processing historical logs
```

**Actions:**
1. Create `.sqrl/` directory
2. Create `.sqrl/memory.db` placeholder
3. Write `.sqrl/config.json` with watcher_enabled: true
4. Add `.sqrl/` to `.gitignore`
5. Install system service (systemd/launchd/Task Scheduler)
6. Start the watcher daemon
7. If not `--no-history`: process last 30 days of historical logs

---

### CLI-003: sqrl on

Enable the watcher daemon.

**Usage:** `sqrl on`

**Actions:**
1. Update config.json to watcher_enabled: true
2. Install system service if not installed
3. Start the service

---

### CLI-004: sqrl off

Disable the watcher daemon.

**Usage:** `sqrl off`

**Actions:**
1. Update config.json to watcher_enabled: false
2. Stop the service

---

### CLI-005: sqrl goaway

Remove all Squirrel data from project.

**Usage:**
```bash
sqrl goaway          # Interactive confirmation
sqrl goaway --force  # Skip confirmation
sqrl goaway -f       # Skip confirmation (short form)
```

**Actions:**
1. Show what will be removed
2. Prompt for confirmation (unless --force)
3. Stop and uninstall system service
4. Remove `.sqrl/` directory

---

### CLI-006: sqrl config

Open configuration in browser.

**Usage:** `sqrl config`

**Action:** Opens Dashboard in default browser (`http://localhost:9741`).

---

### CLI-007: sqrl status

Show Squirrel status for current project.

**Usage:** `sqrl status`

**Output:**
```
Squirrel Status
  Project: /home/user/myproject
  Initialized: yes
  Daemon: running
  Memories: 12 project, 5 user styles
  Last activity: 2 minutes ago
```

**Exit codes:**
| Code | Meaning |
|------|---------|
| 0 | Project initialized, daemon running |
| 1 | Project not initialized |
| 2 | Project initialized, daemon not running |

---

## Agent File Integration

### Managed Block Format

Squirrel manages a block in agent config files:

```markdown
<!-- START Squirrel User Style -->
## Development Style (managed by Squirrel)

- Prefer async/await over callbacks
- Never use emoji in code or comments
- Commits should use minimal English
- AI should maintain critical, calm attitude

<!-- END Squirrel User Style -->
```

**Rules:**
- Only modify content between markers
- Never touch content outside markers
- Create markers if they don't exist
- Append to end of file if new

### Supported Files

| Tool | File |
|------|------|
| Claude Code | `~/.claude/CLAUDE.md`, `<repo>/CLAUDE.md` |
| Cursor | `~/.cursor/rules/*.mdc`, `<repo>/.cursorrules` |
| Codex CLI | `~/.codex/instructions.md` |
| Gemini CLI | `~/.gemini/instructions.md` |

---

## Dashboard API

### Auth

```
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

### User Style

```
GET  /api/style              # List user styles
POST /api/style              # Add style
PUT  /api/style/:id          # Update style
DELETE /api/style/:id        # Delete style
```

### Project Memory

```
GET  /api/projects                           # List projects
GET  /api/projects/:id/memories              # List memories
POST /api/projects/:id/memories              # Add memory
PUT  /api/projects/:id/memories/:mid         # Update memory
DELETE /api/projects/:id/memories/:mid       # Delete memory
GET  /api/projects/:id/categories            # List categories
POST /api/projects/:id/categories            # Add category
```

### Team (B2B)

```
GET  /api/team                    # Get team info
GET  /api/team/members            # List members
POST /api/team/members            # Invite member
DELETE /api/team/members/:id      # Remove member
GET  /api/team/style              # Get team style
PUT  /api/team/style              # Update team style
```

---

## Dashboard UI

### UI-001: Design System

**Color Palette:**

| Role | Color | Usage |
|------|-------|-------|
| Background | `#FFFFFF` | Main background |
| Surface | `#FAFAFA` | Cards, panels |
| Border | `#E5E5E5` | Dividers, borders |
| Text Primary | `#171717` | Headings, body |
| Text Secondary | `#737373` | Labels, hints |
| Accent | `#000000` | Buttons, links, focus |
| Error | `#DC2626` | Error states only |
| Success | `#16A34A` | Success states only |

**Typography:**

| Element | Font | Size | Weight |
|---------|------|------|--------|
| H1 | Inter | 24px | 600 |
| H2 | Inter | 18px | 600 |
| Body | Inter | 14px | 400 |
| Label | Inter | 12px | 500 |
| Mono | JetBrains Mono | 13px | 400 |

**Components:**

| Component | Style |
|-----------|-------|
| Buttons | Black fill, white text, 6px radius |
| Inputs | White fill, 1px border, 6px radius |
| Cards | White fill, 1px border, 8px radius, subtle shadow |
| Tables | Minimal, no zebra striping, 1px bottom borders |

**Principles:**
- Minimal, clean aesthetic
- High contrast for readability
- No decorative elements
- Generous whitespace
- Black & white with color only for status indicators

---

### UI-002: Dashboard Pages

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Squirrel                          [User] [Logout]  │
├──────────────┬──────────────────────────────────────┤
│              │                                      │
│  User Styles │   [Content Area]                     │
│  Projects    │                                      │
│  Settings    │                                      │
│              │                                      │
└──────────────┴──────────────────────────────────────┘
```

**Pages:**

| Page | Path | Content |
|------|------|---------|
| User Styles | `/styles` | List, add, edit, delete user styles |
| Projects | `/projects` | List projects with memory counts |
| Project Detail | `/projects/:id` | Memories grouped by category |
| Settings | `/settings` | Daemon config, sync targets |

---

### UI-003: Dashboard Server

**Port:** `9741` (default, configurable)

**Tech Stack:**
- Rust (axum) for API + static file serving
- Vanilla JS or minimal framework for frontend
- SQLite for data (same as daemon)

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve dashboard SPA |
| GET | `/api/status` | Daemon status |
| GET | `/api/styles` | List user styles |
| POST | `/api/styles` | Add user style |
| DELETE | `/api/styles/:id` | Delete user style |
| GET | `/api/projects` | List projects |
| GET | `/api/projects/:id/memories` | List project memories |
| POST | `/api/projects/:id/memories` | Add memory |
| DELETE | `/api/projects/:id/memories/:mid` | Delete memory |

---

## Error Codes

| Code | Message | Description |
|------|---------|-------------|
| -32001 | Project not initialized | No .sqrl/ directory |
| -32002 | Daemon not running | Daemon process not found |
| -32003 | LLM error | LLM API call failed |
| -32004 | Invalid project root | Path doesn't exist |
| -32005 | No memories found | Project has no memories |
