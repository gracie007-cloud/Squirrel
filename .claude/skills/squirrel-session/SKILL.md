---
name: squirrel-session
description: Load user preferences and project context from Squirrel memory at session start. Use when starting a new coding session.
user-invocable: false
---

At the start of this session, load context from Squirrel:

1. Call `squirrel_get_memory` with type "preference" to get user preferences.
2. Apply these preferences throughout the session.
3. If doc debt exists (check via `sqrl status` output in project), note which docs may need updates.
