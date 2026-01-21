# Squirrel Prompts

All LLM prompts with stable IDs and model tier assignments.

## Model Configuration

Squirrel uses Gemini 3.0 Flash for both stages. Configured via LiteLLM.

| Stage | Default Model |
|-------|---------------|
| User Scanner | `gemini/gemini-3.0-flash` |
| Memory Extractor | `gemini/gemini-3.0-flash` |

**Configuration:** Users can override via `SQRL_CHEAP_MODEL` and `SQRL_STRONG_MODEL` environment variables.

**No embedding model** - v1 uses simple use_count ordering, no semantic search.

---

## PROMPT-001: User Scanner

**Model:** `gemini/gemini-3.0-flash` (configurable via `SQRL_CHEAP_MODEL`)

**ID:** PROMPT-001-USER-SCANNER

**Purpose:** Scan user messages only (no AI messages) to detect if any message indicates a correction or preference worth remembering.

**Core Insight:** Only process user messages first (minimal tokens). If correction detected, pull AI context later.

**Input Variables:**

| Variable | Type | Description |
|----------|------|-------------|
| user_messages | array | List of user messages only (no AI responses) |

**System Prompt:**
```
You scan user messages to detect if the user corrected the AI or stated a preference.

Look for signals like corrections, frustration, or preference statements.

Skip messages that are just acknowledgments ("ok", "sure", "continue", "looks good").

OUTPUT (JSON only):
{
  "needs_context": true | false,
  "trigger_index": <index of the message that triggered, or null if needs_context is false>
}
```

**User Prompt Template:**
```
USER MESSAGES:
{user_messages}

Does any message indicate a correction or preference? Return JSON only.
```

---

## PROMPT-002: Memory Extractor

**Model:** `gemini/gemini-3.0-flash` (configurable via `SQRL_STRONG_MODEL`)

**ID:** PROMPT-002-MEMORY-EXTRACTOR

**Purpose:** Extract memories from user corrections. Distinguish between global preferences and project-specific AI mistakes.

**Core Insight:** All memories come from user corrections. The question is: is this a global preference or a project-specific issue?

**Input Variables:**

| Variable | Type | Description |
|----------|------|-------------|
| trigger_message | string | The user message that triggered (from User Scanner) |
| ai_context | string | The 3 AI turns before the trigger message |
| project_id | string | Project identifier |
| project_root | string | Absolute path to project |
| existing_user_styles | array | Current user style items |
| existing_project_memories | array | Current project memories by category |

**AI Turn Definition:** One AI turn = all content between two user messages (AI responses + tool calls + tool results).

**System Prompt:**
```
You are the Memory Extractor for Squirrel, a coding memory system.

You receive a user message that may contain a correction, along with recent AI context.

## Two Types of Memories

### 1. User Styles (Global Preferences)
Preferences that apply to ALL projects. Synced to agent.md files automatically.

### 2. Project Memories (Project-Specific)
Knowledge specific to THIS project. User triggers via MCP when needed.

## Decision
- User's general preference? → User Style
- Project-specific technical issue? → Project Memory
- Not sure? → Project Memory (safer default)
- Not worth remembering? → Return empty arrays

## Operations

| Op | When to Use |
|----|-------------|
| ADD | New memory not in existing |
| UPDATE | Modifies existing (provide target_id) |
| DELETE | Existing is now wrong (provide target_id) |

## Output Format (JSON only)

{
  "user_styles": [
    { "op": "ADD", "text": "preference" },
    { "op": "UPDATE", "target_id": "id", "text": "updated" },
    { "op": "DELETE", "target_id": "id" }
  ],
  "project_memories": [
    { "op": "ADD", "category": "frontend|backend|docs_test|other", "text": "memory" },
    { "op": "UPDATE", "target_id": "id", "text": "updated" },
    { "op": "DELETE", "target_id": "id" }
  ]
}

If not worth remembering:
{
  "user_styles": [],
  "project_memories": [],
  "skip_reason": "why"
}
```

**User Prompt Template:**
```
PROJECT: {project_id}
PROJECT ROOT: {project_root}

EXISTING USER STYLES:
{existing_user_styles}

EXISTING PROJECT MEMORIES:
{existing_project_memories}

AI CONTEXT (3 turns before trigger):
{ai_context}

USER MESSAGE (trigger):
{trigger_message}

Extract memories if worth remembering. Return JSON only.
```

---

## Token Budgets

| Prompt ID | Max Input | Max Output |
|-----------|-----------|------------|
| PROMPT-001 (User Scanner) | 4000 | 200 |
| PROMPT-002 (Memory Extractor) | 8000 | 2000 |

---

## Error Handling

All prompts must handle:

| Error | Action |
|-------|--------|
| Rate limit | Exponential backoff, max 3 retries |
| Invalid JSON | Re-prompt with stricter format instruction |
| Timeout | Log, return empty result, don't block |
| Content filter | Log, skip memory, continue |

---

## Deprecated Prompts

| Old Prompt | Status |
|------------|--------|
| PROMPT-001-LOG-CLEANER | Replaced by PROMPT-001-USER-SCANNER |
| PROMPT-001-MEMORY-WRITER | Replaced by PROMPT-001 + PROMPT-002 pipeline |
| PROMPT-002-COMPOSE | Removed |
| PROMPT-003-CONFLICT | Removed |
| PROMPT-004-CLI | Removed |
| PROMPT-005-PREFERENCE | Removed |
