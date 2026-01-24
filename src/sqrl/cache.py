"""Simple file-based cache for project summaries.

v1: JSON file at ~/.sqrl/project_summaries.json
"""

import json
from pathlib import Path

CACHE_DIR = Path.home() / ".sqrl"
SUMMARY_CACHE_FILE = CACHE_DIR / "project_summaries.json"


def _ensure_cache_dir() -> None:
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_project_summary(project_root: str) -> str | None:
    """Get cached project summary.

    Args:
        project_root: Absolute path to the project.

    Returns:
        Cached summary string, or None if not cached.
    """
    if not SUMMARY_CACHE_FILE.exists():
        return None

    try:
        cache = json.loads(SUMMARY_CACHE_FILE.read_text())
        return cache.get(project_root)
    except (json.JSONDecodeError, OSError):
        return None


def set_project_summary(project_root: str, summary: str) -> None:
    """Cache a project summary.

    Args:
        project_root: Absolute path to the project.
        summary: The summary string to cache.
    """
    _ensure_cache_dir()

    cache: dict[str, str] = {}
    if SUMMARY_CACHE_FILE.exists():
        try:
            cache = json.loads(SUMMARY_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            cache = {}

    cache[project_root] = summary
    SUMMARY_CACHE_FILE.write_text(json.dumps(cache, indent=2))


def clear_project_summary(project_root: str) -> None:
    """Remove a project summary from cache.

    Args:
        project_root: Absolute path to the project.
    """
    if not SUMMARY_CACHE_FILE.exists():
        return

    try:
        cache = json.loads(SUMMARY_CACHE_FILE.read_text())
        if project_root in cache:
            del cache[project_root]
            SUMMARY_CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except (json.JSONDecodeError, OSError):
        pass
