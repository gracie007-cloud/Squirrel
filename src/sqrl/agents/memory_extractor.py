"""PROMPT-002: Memory Extractor agent."""

import json
import os

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from sqrl.models.episode import ExistingProjectMemory, ExistingUserStyle
from sqrl.models.extraction import ExtractorOutput

SYSTEM_PROMPT = """You are the Memory Extractor for Squirrel, a coding memory system.

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
}"""


def _get_model() -> OpenAIModel:
    """Get model configured for OpenRouter."""
    model_name = os.getenv("SQRL_STRONG_MODEL", "google/gemini-2.0-flash-001")
    api_key = os.getenv("OPENROUTER_API_KEY")
    provider = OpenAIProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    return OpenAIModel(model_name, provider=provider)


class MemoryExtractor:
    """Memory Extractor agent using PydanticAI."""

    def __init__(self) -> None:
        self.agent = Agent(
            model=_get_model(),
            system_prompt=SYSTEM_PROMPT,
            output_type=ExtractorOutput,
            retries=3,
        )

    async def extract(
        self,
        project_id: str,
        project_root: str,
        trigger_message: str,
        ai_context: str,
        existing_user_styles: list[ExistingUserStyle],
        existing_project_memories: list[ExistingProjectMemory],
    ) -> ExtractorOutput:
        """Extract memories from user message with AI context."""
        styles_json = json.dumps(
            [{"id": s.id, "text": s.text} for s in existing_user_styles],
            indent=2,
        )
        memories_json = json.dumps(
            [
                {
                    "id": m.id,
                    "category": m.category,
                    "subcategory": m.subcategory,
                    "text": m.text,
                }
                for m in existing_project_memories
            ],
            indent=2,
        )

        user_prompt = f"""PROJECT: {project_id}
PROJECT ROOT: {project_root}

EXISTING USER STYLES:
{styles_json}

EXISTING PROJECT MEMORIES:
{memories_json}

AI CONTEXT (3 turns before trigger):
{ai_context}

USER MESSAGE (trigger):
{trigger_message}

Extract memories if worth remembering. Return JSON only."""

        result = await self.agent.run(user_prompt)
        return result.output
