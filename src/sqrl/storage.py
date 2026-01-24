"""SQLite storage for user styles and project memories.

SCHEMA-001: user_styles in ~/.sqrl/user_style.db
SCHEMA-002: project_memories in <repo>/.sqrl/memory.db
"""

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SQRL_DIR = Path.home() / ".sqrl"
USER_STYLE_DB = SQRL_DIR / "user_style.db"

USER_STYLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_styles (
  id          TEXT PRIMARY KEY,
  text        TEXT NOT NULL UNIQUE,
  use_count   INTEGER DEFAULT 1,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_styles_use_count ON user_styles(use_count DESC);
"""

PROJECT_MEMORIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS project_memories (
  id           TEXT PRIMARY KEY,
  category     TEXT NOT NULL,
  subcategory  TEXT NOT NULL DEFAULT 'main',
  text         TEXT NOT NULL,
  use_count    INTEGER DEFAULT 1,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_project_memories_category ON project_memories(category);
CREATE INDEX IF NOT EXISTS idx_project_memories_use_count ON project_memories(use_count DESC);
"""


@dataclass
class UserStyle:
    """A user style preference."""

    id: str
    text: str
    use_count: int
    created_at: str
    updated_at: str


@dataclass
class ProjectMemory:
    """A project-specific memory."""

    id: str
    category: str
    subcategory: str
    text: str
    use_count: int
    created_at: str
    updated_at: str


def _now_iso() -> str:
    """Get current time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """Generate a new UUID."""
    return str(uuid.uuid4())


class UserStyleStorage:
    """Storage for user styles (~/.sqrl/user_style.db)."""

    def __init__(self) -> None:
        SQRL_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = USER_STYLE_DB
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(USER_STYLES_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def add(self, text: str) -> UserStyle:
        """Add a new user style or increment use_count if exists."""
        now = _now_iso()
        with self._conn() as conn:
            # Check if exists
            row = conn.execute(
                "SELECT id, use_count FROM user_styles WHERE text = ?", (text,)
            ).fetchone()

            if row:
                # Increment use_count
                style_id, use_count = row
                new_count = use_count + 1
                conn.execute(
                    "UPDATE user_styles SET use_count = ?, updated_at = ? WHERE id = ?",
                    (new_count, now, style_id),
                )
                return UserStyle(
                    id=style_id,
                    text=text,
                    use_count=new_count,
                    created_at=now,
                    updated_at=now,
                )
            else:
                # Insert new
                style_id = _new_id()
                conn.execute(
                    """INSERT INTO user_styles (id, text, use_count, created_at, updated_at)
                       VALUES (?, ?, 1, ?, ?)""",
                    (style_id, text, now, now),
                )
                return UserStyle(
                    id=style_id,
                    text=text,
                    use_count=1,
                    created_at=now,
                    updated_at=now,
                )

    def get_all(self) -> list[UserStyle]:
        """Get all user styles ordered by use_count."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, text, use_count, created_at, updated_at "
                "FROM user_styles ORDER BY use_count DESC"
            ).fetchall()
            return [UserStyle(*row) for row in rows]

    def delete(self, style_id: str) -> bool:
        """Delete a user style by ID."""
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM user_styles WHERE id = ?", (style_id,)
            )
            return cursor.rowcount > 0


class ProjectMemoryStorage:
    """Storage for project memories (<repo>/.sqrl/memory.db)."""

    def __init__(self, project_root: str) -> None:
        self.project_root = Path(project_root)
        self.sqrl_dir = self.project_root / ".sqrl"
        self.sqrl_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.sqrl_dir / "memory.db"
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(PROJECT_MEMORIES_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def add(self, category: str, text: str, subcategory: str = "main") -> ProjectMemory:
        """Add a new project memory or increment use_count if similar exists."""
        now = _now_iso()
        with self._conn() as conn:
            # Check if exists (same category and text)
            row = conn.execute(
                "SELECT id, use_count FROM project_memories WHERE category = ? AND text = ?",
                (category, text),
            ).fetchone()

            if row:
                # Increment use_count
                memory_id, use_count = row
                new_count = use_count + 1
                conn.execute(
                    "UPDATE project_memories SET use_count = ?, updated_at = ? WHERE id = ?",
                    (new_count, now, memory_id),
                )
                return ProjectMemory(
                    id=memory_id,
                    category=category,
                    subcategory=subcategory,
                    text=text,
                    use_count=new_count,
                    created_at=now,
                    updated_at=now,
                )
            else:
                # Insert new
                memory_id = _new_id()
                conn.execute(
                    """INSERT INTO project_memories
                       (id, category, subcategory, text, use_count, created_at, updated_at)
                       VALUES (?, ?, ?, ?, 1, ?, ?)""",
                    (memory_id, category, subcategory, text, now, now),
                )
                return ProjectMemory(
                    id=memory_id,
                    category=category,
                    subcategory=subcategory,
                    text=text,
                    use_count=1,
                    created_at=now,
                    updated_at=now,
                )

    def get_all(self) -> list[ProjectMemory]:
        """Get all project memories ordered by use_count."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, category, subcategory, text, use_count, created_at, updated_at "
                "FROM project_memories ORDER BY use_count DESC"
            ).fetchall()
            return [ProjectMemory(*row) for row in rows]

    def get_by_category(self, category: str) -> list[ProjectMemory]:
        """Get project memories by category."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, category, subcategory, text, use_count, created_at, updated_at "
                "FROM project_memories WHERE category = ? ORDER BY use_count DESC",
                (category,),
            ).fetchall()
            return [ProjectMemory(*row) for row in rows]

    def get_grouped(self) -> dict[str, list[ProjectMemory]]:
        """Get all memories grouped by category."""
        memories = self.get_all()
        grouped: dict[str, list[ProjectMemory]] = {}
        for m in memories:
            if m.category not in grouped:
                grouped[m.category] = []
            grouped[m.category].append(m)
        return grouped

    def delete(self, memory_id: str) -> bool:
        """Delete a project memory by ID."""
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM project_memories WHERE id = ?", (memory_id,)
            )
            return cursor.rowcount > 0
