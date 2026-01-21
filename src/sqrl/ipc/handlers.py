"""IPC method handlers."""

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from sqrl.agents import MemoryExtractor, UserScanner
from sqrl.models import ProcessEpisodeRequest, ProcessEpisodeResponse
from sqrl.models.episode import EpisodeEvent

log = structlog.get_logger()

Handler = Callable[[dict[str, Any]], Awaitable[Any]]


def _extract_user_messages(events: list[EpisodeEvent]) -> list[str]:
    """Extract just the user messages from events."""
    return [e.content_summary for e in events if e.role == "user"]


def _get_ai_turns(events: list[EpisodeEvent], trigger_index: int) -> str:
    """Get 3 AI turns before the trigger message.

    An AI turn = all events between two user messages.
    """
    # Find all user message indices
    user_indices = [i for i, e in enumerate(events) if e.role == "user"]

    if trigger_index >= len(user_indices):
        return ""

    # The actual event index of the trigger
    trigger_event_idx = user_indices[trigger_index]

    # Find start index for 3 AI turns before
    # Each AI turn is bounded by user messages
    # So we need to go back 3 user messages and collect everything in between
    start_turn = max(0, trigger_index - 3)
    start_event_idx = user_indices[start_turn] if start_turn > 0 else 0

    # Collect all events from start to trigger (excluding trigger itself)
    ai_turn_events = events[start_event_idx:trigger_event_idx]

    # Format as text
    return "\n".join(
        f"[{e.role}] {e.content_summary}" for e in ai_turn_events
    )


async def handle_process_episode(params: dict[str, Any]) -> dict[str, Any]:
    """IPC-001: process_episode handler."""
    # Parse request
    try:
        request = ProcessEpisodeRequest(**params)
    except Exception as e:
        raise ValueError(f"Invalid params: {e}") from e

    log.info(
        "process_episode_start",
        project_id=request.project_id,
        events_count=len(request.events),
    )

    # Stage 1: User Scanner - only scan user messages
    user_messages = _extract_user_messages(request.events)
    if not user_messages:
        log.info("no_user_messages")
        return ProcessEpisodeResponse(
            skipped=True,
            skip_reason="No user messages in episode",
        ).model_dump()

    scanner = UserScanner()
    scanner_output = await scanner.scan(user_messages)

    if not scanner_output.needs_context:
        log.info("no_correction_detected")
        return ProcessEpisodeResponse(
            skipped=True,
            skip_reason="No correction or preference detected",
        ).model_dump()

    # Stage 2: Memory Extractor - with AI context
    trigger_index = scanner_output.trigger_index or 0
    trigger_message = user_messages[trigger_index]
    ai_context = _get_ai_turns(request.events, trigger_index)

    extractor = MemoryExtractor()
    extractor_output = await extractor.extract(
        project_id=request.project_id,
        project_root=request.project_root,
        trigger_message=trigger_message,
        ai_context=ai_context,
        existing_user_styles=request.existing_user_styles,
        existing_project_memories=request.existing_project_memories,
    )

    log.info(
        "process_episode_done",
        user_styles_count=len(extractor_output.user_styles),
        project_memories_count=len(extractor_output.project_memories),
    )

    return ProcessEpisodeResponse(
        skipped=False,
        user_styles=extractor_output.user_styles,
        project_memories=extractor_output.project_memories,
    ).model_dump()


def create_handlers() -> dict[str, Handler]:
    """Create all IPC handlers."""
    return {
        "process_episode": handle_process_episode,
    }
