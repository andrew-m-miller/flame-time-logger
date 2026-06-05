"""Bridge between the Flame ``selection`` and the rest of the app.

Everything that touches the ``flame`` module (only importable inside Flame)
lives here. :func:`build_context` reduces a Flame selection to a plain
:class:`Context` so the dialog and FPT layers stay unit-testable off-Flame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List


@dataclass
class Context:
    """Plain snapshot of the Flame state needed to log time."""

    project_name: str | None = None
    #: Batch-group names from the selection; first is the default shot match.
    shot_names: List[str] = field(default_factory=list)

    @property
    def primary_shot_name(self) -> str | None:
        return self.shot_names[0] if self.shot_names else None


def _current_project_name() -> str | None:
    try:
        import flame  # noqa: PLC0415 -- only available inside Flame
    except ImportError:
        return None

    project = getattr(flame, "project", None)
    current = getattr(project, "current_project", None)
    if current is None:
        return None
    return str(current.name)


def build_context(selection: Iterable[object]) -> Context:
    """Build a :class:`Context` from a Flame media-panel ``selection``.

    ``selection`` is a tuple of Flame PyObjects; the hook only enables the
    action for batch groups (``PyBatch``), so each item exposes a ``name``
    attribute we stringify into a shot-name candidate.
    """
    shot_names: List[str] = []
    for item in selection:
        name = getattr(item, "name", None)
        if name is not None:
            shot_names.append(str(name))

    return Context(project_name=_current_project_name(), shot_names=shot_names)
