"""Flow Production Tracking (ShotGrid) access layer.

Pure Python -- no Qt, no Flame imports -- so it can be swapped for a fake in
tests/smoke runs. Authentication reuses the live ShotGrid Toolkit session via
``sgtk.get_authenticated_user()``; no passwords or tokens are handled here.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

from .stopwatch import round_to_quarter_hour

# Type aliases for ShotGrid entity dicts, e.g. {"type": "Shot", "id": 123}.
Entity = Dict[str, Any]


class FPTError(Exception):
    """Base class for FPT access problems surfaced to the UI."""


class NotAuthenticated(FPTError):
    """Raised when there is no authenticated ShotGrid Toolkit session."""


def task_label(task: Entity) -> str:
    """Human-friendly label for a task combo entry."""
    content = task.get("content") or "Task"
    step = task.get("step")
    step_name = step.get("name") if isinstance(step, dict) else None
    return f"{step_name} / {content}" if step_name else str(content)


class FPTClient:
    """Thin wrapper over a ``shotgun_api3`` connection.

    Construct with no args inside Flame (it self-authenticates), or pass an
    existing ``sg`` connection and ``current_user`` entity for testing.
    """

    def __init__(
        self,
        sg: Any = None,
        current_user: Optional[Entity] = None,
        project: Optional[Entity] = None,
    ) -> None:
        if sg is None:
            sg, current_user = self._connect_from_toolkit()
        self._sg = sg
        self._current_user = current_user
        self._project = project

    @staticmethod
    def _connect_from_toolkit() -> tuple[Any, Entity]:
        try:
            import sgtk  # noqa: PLC0415 -- bundled with Flame's integration
        except ImportError as exc:  # pragma: no cover - env specific
            raise NotAuthenticated(
                "ShotGrid Toolkit (sgtk) is not available in this Flame "
                "session."
            ) from exc

        user = sgtk.get_authenticated_user()
        if user is None:
            raise NotAuthenticated(
                "No authenticated ShotGrid user. Log into the ShotGrid/Flow "
                "integration in Flame and try again."
            )

        sg = user.create_sg_connection()
        human = sg.find_one(
            "HumanUser", [["login", "is", user.login]], ["id", "name"]
        )
        if human is None:
            raise NotAuthenticated(
                f"No HumanUser found for login '{user.login}' on this site."
            )
        return sg, human

    @property
    def current_user(self) -> Entity:
        return self._current_user

    # -- lookups ---------------------------------------------------------

    def current_project(self) -> Entity:
        """Project entity for the active sgtk session, from the engine context.

        This is the authoritative FPT project (``{type, id, name}``) for the
        running Flame integration -- no name matching against the Flame project
        is needed. Cached after first read.
        """
        if self._project is None:
            self._project = self._project_from_engine()
        return self._project

    @staticmethod
    def _project_from_engine() -> Entity:
        import sgtk  # noqa: PLC0415 -- bundled with Flame's integration

        engine = sgtk.platform.current_engine()
        if engine is None:
            raise NotAuthenticated(
                "No active ShotGrid Toolkit engine in this Flame session."
            )
        context = engine.context
        project = context.project if context is not None else None
        if not project:
            raise FPTError(
                "The current ShotGrid Toolkit context has no project."
            )
        return project

    def find_shot(self, project: Entity, code: Optional[str]) -> Optional[Entity]:
        """Exact ``code`` match for a Shot within ``project``."""
        if not code:
            return None
        return self._sg.find_one(
            "Shot",
            [["project", "is", project], ["code", "is", code]],
            ["id", "code"],
        )

    def list_shots(self, project: Entity) -> List[Entity]:
        """All shots in a project, for the searchable fallback dropdown."""
        return self._sg.find(
            "Shot",
            [["project", "is", project]],
            ["id", "code"],
            order=[{"field_name": "code", "direction": "asc"}],
        )

    def list_tasks(self, shot: Entity) -> List[Entity]:
        """Tasks attached to a shot, for the Task dropdown."""
        return self._sg.find(
            "Task",
            [["entity", "is", shot]],
            ["id", "content", "step"],
            order=[{"field_name": "content", "direction": "asc"}],
        )

    # -- writes ----------------------------------------------------------

    def create_time_log(
        self,
        project: Entity,
        task: Entity,
        minutes: float,
        date: Optional[_dt.date] = None,
        description: str = "",
    ) -> Entity:
        """Create a TimeLog against ``task``, rounded to the nearest 15 min.

        ``duration`` is stored in minutes; ``date`` defaults to today.
        """
        rounded = round_to_quarter_hour(minutes)
        when = date or _dt.date.today()
        return self._sg.create(
            "TimeLog",
            {
                "project": project,
                "entity": task,
                "user": self._current_user,
                "duration": rounded,
                "date": when.strftime("%Y-%m-%d"),
                "description": description,
            },
        )
