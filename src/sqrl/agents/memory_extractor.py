"""PROMPT-002: Memory Extractor agent."""

import json
import os

from openai import AsyncOpenAI

from sqrl.models.episode import ExistingProjectMemory, ExistingUserStyle
from sqrl.models.extraction import ExtractorOutput

SYSTEM_PROMPT = """Extract memories from user corrections. Output JSON only.

User Style = global preference (all projects)
Project Memory = this project only

Example output:
{"user_styles": [{"op": "ADD", "text": "never use emoji"}], "project_memories": []}

Another example:
{"user_styles": [], "project_memories": [{"op": "ADD", "category": "backend", "text": "use httpx"}]}

Rules:
- Each item MUST be an object with "op" and "text" fields
- op: "ADD", "UPDATE", or "DELETE"
- category (project only): "frontend", "backend", "docs_test", "other"
- Return empty arrays if not worth remembering"""


class MemoryExtractor:
    """Memory Extractor using raw OpenAI client."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        self.model = os.getenv("SQRL_STRONG_MODEL", "google/gemini-2.0-flash-001")

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
        )
        memories_json = json.dumps(
            [
                {"id": m.id, "category": m.category, "text": m.text}
                for m in existing_project_memories
            ],
        )

        user_prompt = f"""PROJECT: {project_id}

EXISTING USER STYLES: {styles_json}
EXISTING PROJECT MEMORIES: {memories_json}

AI CONTEXT:
{ai_context}

USER MESSAGE:
{trigger_message}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content or "{}"
        # Extract JSON from response (may be wrapped in markdown)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            data = json.loads(content.strip())
            return ExtractorOutput(**data)
        except (json.JSONDecodeError, ValueError):
            return ExtractorOutput()
