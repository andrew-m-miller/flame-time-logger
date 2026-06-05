"""Bridge between the Flame ``selection`` and the rest of the app.

Everything that touches the ``flame`` module (only importable inside Flame)
lives here. :func:`build_context` reduces a Flame selection to a plain
:class:`Context` so the dialog and FPT layers stay unit-testable off-Flame.

The FPT project is *not* derived here -- it comes from the live sgtk engine
context (see :meth:`flame_time_logger.fpt.FPTClient.current_project`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List


@dataclass
class Context:
    """Plain snapshot of the Flame selection needed to log time."""

    #: Batch-group names from the selection; first is the default shot match.
    shot_names: List[str] = field(default_factory=list)

    @property
    def primary_shot_name(self) -> str | None:
        return self.shot_names[0] if self.shot_names else None


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

    return Context(shot_names=shot_names)
