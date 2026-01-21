"""PROMPT-001: User Scanner agent."""

import json
import os

from openai import AsyncOpenAI

from sqrl.models.extraction import ScannerOutput

SYSTEM_PROMPT = """You scan user messages to detect corrections or preferences.

Look for signals like corrections, frustration, or preference statements.

Skip messages that are just acknowledgments ("ok", "sure", "continue", "looks good").

Output JSON only:
{"needs_context": true, "trigger_index": 1}
or
{"needs_context": false, "trigger_index": null}"""


class UserScanner:
    """User Scanner using raw OpenAI client."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        self.model = os.getenv("SQRL_CHEAP_MODEL", "google/gemini-2.0-flash-001")

    async def scan(self, user_messages: list[str]) -> ScannerOutput:
        """Scan user messages for correction signals."""
        messages_text = "\n".join(
            f"[{i}] {msg}" for i, msg in enumerate(user_messages)
        )
        user_prompt = f"""USER MESSAGES:
{messages_text}

Does any message indicate a correction or preference? Return JSON only."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content or "{}"
        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        try:
            data = json.loads(content.strip())
            return ScannerOutput(**data)
        except (json.JSONDecodeError, ValueError):
            return ScannerOutput(needs_context=False)
