"""Optional configuration for the time logger.

Authentication needs no config (it comes from the live sgtk session). This is
only for nicety/overrides: a ``site`` URL used in log messages, and an optional
Flame-project-name -> FPT-project-name map for studios whose names differ.

Lookup order for the settings file:
  1. ``$FLAME_TIME_LOGGER_CONFIG`` if set
  2. ``~/.flame_time_logger/settings.json``
  3. ``config/settings.json`` next to the repo
A missing file is fine -- defaults are used.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class Config:
    site: str | None = None
    #: Flame project name -> FPT project name overrides.
    project_map: Dict[str, str] = field(default_factory=dict)

    def fpt_project_name(self, flame_project_name: str | None) -> str | None:
        """Map a Flame project name to its FPT name, or pass it through."""
        if flame_project_name is None:
            return None
        return self.project_map.get(flame_project_name, flame_project_name)


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []
    env = os.environ.get("FLAME_TIME_LOGGER_CONFIG")
    if env:
        paths.append(Path(env))
    paths.append(Path.home() / ".flame_time_logger" / "settings.json")
    paths.append(Path(__file__).resolve().parent.parent / "config" / "settings.json")
    return paths


def load_config() -> Config:
    """Load the first settings file found, else return defaults."""
    for path in _candidate_paths():
        try:
            if path.is_file():
                data = json.loads(path.read_text())
                return Config(
                    site=data.get("site"),
                    project_map=dict(data.get("project_map", {})),
                )
        except (OSError, ValueError):
            # Corrupt/unreadable config should never block logging time.
            continue
    return Config()
