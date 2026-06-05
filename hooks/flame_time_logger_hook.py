"""Flame Python hook: a Media Panel action to log time against a batch group.

Install: add this file's directory to Flame's hook path (e.g.
``DL_PYTHON_HOOK_PATH``) and make sure the repository root is importable
(see README). Flame discovers ``get_media_panel_custom_ui_actions`` here.
"""

from __future__ import annotations

import os
import sys

import flame  # provided by Flame at runtime

# Ensure the package (one level up from hooks/) is importable.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _is_batch_group(selection) -> bool:
    """Show the action only when the whole selection is batch groups."""
    return len(selection) > 0 and all(
        isinstance(item, flame.PyBatch) for item in selection
    )


def _log_time(selection) -> None:
    # Import lazily so a broken dependency cannot stop Flame loading hooks.
    from flame_time_logger.app import launch_dialog
    from flame_time_logger.flame_context import build_context

    launch_dialog(build_context(selection))


def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "Time Logger",
            "actions": [
                {
                    "name": "Log Time...",
                    "isVisible": _is_batch_group,
                    "execute": _log_time,
                    "minimumVersion": "2026.0.0.0",
                }
            ],
        }
    ]
