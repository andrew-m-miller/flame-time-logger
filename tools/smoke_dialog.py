"""Standalone smoke test for the dialog: no Flame, no live ShotGrid.

Run on a workstation that has PySide6 installed:

    python tools/smoke_dialog.py

It launches the real TimeLogDialog against a fake FPTClient that returns canned
shots/tasks and prints the TimeLog payload it would create. Exercises the timer,
shot->task repopulation, quarter-hour rounding preview, and submit flow.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flame_time_logger.app import launch_dialog  # noqa: E402
from flame_time_logger.flame_context import Context  # noqa: E402


class FakeFPTClient:
    """Mimics flame_time_logger.fpt.FPTClient with in-memory data."""

    def __init__(self):
        self._project = {"type": "Project", "id": 1, "name": "Demo"}
        self._shots = [
            {"type": "Shot", "id": 10, "code": "SHOT_0010"},
            {"type": "Shot", "id": 20, "code": "SHOT_0020"},
            {"type": "Shot", "id": 30, "code": "BG_0100"},
        ]
        self._tasks = {
            10: [
                {"type": "Task", "id": 101, "content": "comp",
                 "step": {"type": "Step", "id": 1, "name": "Comp"}},
                {"type": "Task", "id": 102, "content": "paint",
                 "step": {"type": "Step", "id": 2, "name": "Paint"}},
            ],
            20: [{"type": "Task", "id": 201, "content": "comp",
                  "step": {"type": "Step", "id": 1, "name": "Comp"}}],
            30: [],
        }

    @property
    def current_user(self):
        return {"type": "HumanUser", "id": 5, "name": "Demo Artist"}

    def current_project(self):
        return self._project

    def find_shot(self, project, code):
        return next((s for s in self._shots if s["code"] == code), None)

    def list_shots(self, project):
        return list(self._shots)

    def list_tasks(self, shot):
        return list(self._tasks.get(shot["id"], []))

    def create_time_log(self, project, task, minutes, date=None, description=""):
        from flame_time_logger.stopwatch import round_to_quarter_hour

        payload = {
            "project": project,
            "entity": task,
            "user": self.current_user,
            "duration": round_to_quarter_hour(minutes),
            "date": str(date),
            "description": description,
        }
        print("\n--- TimeLog that would be created ---")
        for key, value in payload.items():
            print(f"  {key}: {value}")
        return {"type": "TimeLog", "id": 999, **payload}


def main():
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    context = Context(shot_names=["SHOT_0010"])
    dialog = launch_dialog(context, client_factory=FakeFPTClient)
    dialog.exec()  # block in standalone mode


if __name__ == "__main__":
    main()
