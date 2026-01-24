"""Style Syncer - writes user styles to agent.md files.

Syncs user styles from database to:
1. ~/.sqrl/personal-style.md (always)
2. Claude Code: ~/.claude/CLAUDE.md (global) or <project>/.claude/CLAUDE.md
3. Codex: <project>/AGENTS.md

Note: For v1, we append a Squirrel section to existing files rather than
managing the entire file content.
"""

from pathlib import Path

from sqrl.storage import UserStyleStorage

SQRL_DIR = Path.home() / ".sqrl"
PERSONAL_STYLE_FILE = SQRL_DIR / "personal-style.md"

# Agent config file locations
CLAUDE_GLOBAL_DIR = Path.home() / ".claude"
CLAUDE_GLOBAL_MD = CLAUDE_GLOBAL_DIR / "CLAUDE.md"

# Marker for Squirrel-managed section
SECTION_START = "<!-- SQUIRREL:START -->"
SECTION_END = "<!-- SQUIRREL:END -->"


def _format_styles_markdown(styles: list[str]) -> str:
    """Format user styles as markdown bullet list."""
    if not styles:
        return ""
    lines = ["## User Preferences (Squirrel)", ""]
    for style in styles:
        lines.append(f"- {style}")
    return "\n".join(lines)


def _update_section_in_file(file_path: Path, content: str) -> None:
    """Update the Squirrel section in a file, preserving other content."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_path.exists():
        existing = file_path.read_text()
    else:
        existing = ""

    # Build new section
    new_section = f"{SECTION_START}\n{content}\n{SECTION_END}"

    if SECTION_START in existing and SECTION_END in existing:
        # Replace existing section
        start_idx = existing.index(SECTION_START)
        end_idx = existing.index(SECTION_END) + len(SECTION_END)
        updated = existing[:start_idx] + new_section + existing[end_idx:]
    else:
        # Append new section
        if existing and not existing.endswith("\n"):
            existing += "\n"
        if existing:
            existing += "\n"
        updated = existing + new_section + "\n"

    file_path.write_text(updated)


def _write_personal_style(styles: list[str]) -> None:
    """Write styles to ~/.sqrl/personal-style.md."""
    SQRL_DIR.mkdir(parents=True, exist_ok=True)
    content = _format_styles_markdown(styles)
    PERSONAL_STYLE_FILE.write_text(content + "\n")


def sync_user_styles(project_root: str | None = None) -> dict[str, bool]:
    """Sync user styles from database to agent config files.

    Args:
        project_root: Optional project path for project-level syncing.

    Returns:
        Dict mapping file paths to success status.
    """
    storage = UserStyleStorage()
    all_styles = storage.get_all()
    style_texts = [s.text for s in all_styles]

    results: dict[str, bool] = {}

    # 1. Always write personal-style.md
    try:
        _write_personal_style(style_texts)
        results[str(PERSONAL_STYLE_FILE)] = True
    except OSError:
        results[str(PERSONAL_STYLE_FILE)] = False

    # 2. Update global Claude CLAUDE.md if it exists
    if CLAUDE_GLOBAL_MD.exists():
        try:
            content = _format_styles_markdown(style_texts)
            _update_section_in_file(CLAUDE_GLOBAL_MD, content)
            results[str(CLAUDE_GLOBAL_MD)] = True
        except OSError:
            results[str(CLAUDE_GLOBAL_MD)] = False

    # 3. Update project-level files if project_root provided
    if project_root:
        project_path = Path(project_root)

        # Claude Code project-level: <project>/.claude/CLAUDE.md
        claude_project_md = project_path / ".claude" / "CLAUDE.md"
        if claude_project_md.exists():
            try:
                content = _format_styles_markdown(style_texts)
                _update_section_in_file(claude_project_md, content)
                results[str(claude_project_md)] = True
            except OSError:
                results[str(claude_project_md)] = False

        # Codex: <project>/AGENTS.md
        agents_md = project_path / "AGENTS.md"
        if agents_md.exists():
            try:
                content = _format_styles_markdown(style_texts)
                _update_section_in_file(agents_md, content)
                results[str(agents_md)] = True
            except OSError:
                results[str(agents_md)] = False

    return results
