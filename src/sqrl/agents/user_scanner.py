"""PROMPT-001: User Scanner agent."""

import os

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from sqrl.models.extraction import ScannerOutput

SYSTEM_PROMPT = """You scan user messages to detect corrections or preferences.

Look for signals like corrections, frustration, or preference statements.

Skip messages that are just acknowledgments ("ok", "sure", "continue", "looks good").

OUTPUT (JSON only):
{
  "needs_context": true | false,
  "trigger_index": <index of the message that triggered, or null if needs_context is false>
}"""


def _get_model() -> OpenAIModel:
    """Get model configured for OpenRouter."""
    model_name = os.getenv("SQRL_CHEAP_MODEL", "google/gemini-2.0-flash-001")
    api_key = os.getenv("OPENROUTER_API_KEY")
    provider = OpenAIProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    return OpenAIModel(model_name, provider=provider)


class UserScanner:
    """User Scanner agent using PydanticAI."""

    def __init__(self) -> None:
        self.agent = Agent(
            model=_get_model(),
            system_prompt=SYSTEM_PROMPT,
            output_type=ScannerOutput,
            retries=3,
        )

    async def scan(self, user_messages: list[str]) -> ScannerOutput:
        """Scan user messages for correction signals."""
        messages_text = "\n".join(
            f"[{i}] {msg}" for i, msg in enumerate(user_messages)
        )
        user_prompt = f"""USER MESSAGES:
{messages_text}

Does any message indicate a correction or preference? Return JSON only."""

        result = await self.agent.run(user_prompt)
        return result.output
