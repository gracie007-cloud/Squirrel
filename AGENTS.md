# Squirrel Project

Local-first memory system for AI coding tools.

## Architecture

Single Rust binary (`sqrl`). No daemon, no Python, no LLM calls.

```
CLI AI (Claude Code, Cursor, etc.)
    │ MCP
    ▼
sqrl binary (Rust)
    │
    ▼
SQLite (.sqrl/memory.db)
```

| Component | Responsibility | Never Does |
|-----------|----------------|------------|
| sqrl binary | MCP server, CLI, git hooks, SQLite | LLM calls, file watching, daemon |
| CLI AI | Decides what to store, fixes doc debt | Direct DB access |

## Spec-Driven Development

Specs are source of truth. Code is compiled output.

| Spec File | Purpose |
|-----------|---------|
| specs/CONSTITUTION.md | Project governance, core principles |
| specs/ARCHITECTURE.md | System boundaries, data flow |
| specs/SCHEMAS.md | Database schemas (SCHEMA-*) |
| specs/INTERFACES.md | MCP, CLI contracts (MCP-*, CLI-*) |
| specs/DECISIONS.md | Architecture decision records (ADR-*) |

**Rules:**
1. Read specs before implementing
2. Never implement behavior not defined in specs
3. Update specs before or with code, never after
4. Reference spec IDs in commits

## AI Workflow

| Phase | Action | Output |
|-------|--------|--------|
| 1. Specify | Define WHAT and WHY | `specs/*.md` updated |
| 2. Clarify | Ask questions, resolve ambiguities | Ambiguities resolved |
| 3. Plan | Define HOW | Implementation plan |
| 4. Tasks | Break into ordered steps | Task list |
| 5. Implement | Execute one task at a time | Working code |

## Stop and Discuss

Do NOT decide these on your own:
- Model selection (which LLM to use)
- Numeric values (thresholds, limits, timeouts)
- Prompts (system prompts, extraction prompts)
- Any non-trivial design decisions

## Development Environment

Uses Nix via devenv (ADR-006):

```bash
devenv shell
```

## Team Standards

- English only in code, comments, commits
- No emojis in documentation
- Brief, direct language
- Tables over paragraphs
- Branch: `yourname/type-description`
- Commit: `type(scope): brief description`
- Keep files under 200 lines
- Only change what's necessary (DR5)
- Write tests for new features (DR4)

## Doc Debt Awareness

Squirrel auto-installs git hooks that track doc debt. After each commit, check `sqrl status` to see if docs need updates.

| Files Changed | Check These Docs |
|---------------|------------------|
| `*.rs` (Rust) | `specs/ARCHITECTURE.md`, `specs/INTERFACES.md`, `specs/SCHEMAS.md` |
| `specs/*.md` | Related code that implements the spec |
| `*.toml`, `*.nix` | `specs/DECISIONS.md` (if config change is significant) |

When doc debt is detected, update the related docs before pushing.

<!-- START Squirrel Memory Protocol -->
## Squirrel Memory Protocol

You have access to Squirrel memory tools via MCP.

### When to store memories (squirrel_store_memory):
- User states a preference → type: "preference"
- You learn a project-specific fact → type: "project"
- Architecture/design decision is made → type: "decision"
- A problem is solved → type: "solution"

### When to retrieve memories (squirrel_get_memory):
- When user asks for project context
- When you need to recall past decisions
- When starting work on a component you've worked on before

### Rules:
- Store memories proactively. Don't ask permission.
- Even if a memory seems redundant, store it. Squirrel handles deduplication.
- Keep memory content concise (1-2 sentences).
- Always include relevant tags.
<!-- END Squirrel Memory Protocol -->
