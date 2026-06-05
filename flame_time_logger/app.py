"""Launch entry point for the dialog, called from the Flame hook.

Reuses the ``QApplication`` Flame already runs and keeps a module-level
reference to the dialog so it is not garbage-collected while shown.
"""

from __future__ import annotations

from typing import Optional

from .dialog import ClientFactory, TimeLogDialog
from .fpt import FPTClient
from .flame_context import Context

# Hold a reference so the non-modal dialog survives past launch_dialog().
_dialog: Optional[TimeLogDialog] = None


def launch_dialog(
    context: Context, client_factory: ClientFactory = FPTClient
) -> TimeLogDialog:
    """Create and show the time-logging dialog (non-modal)."""
    from PySide6 import QtWidgets

    # Inside Flame an instance already exists; this keeps standalone runs working.
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    global _dialog
    _dialog = TimeLogDialog(context, client_factory=client_factory)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    return _dialog
