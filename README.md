# Flame Time Logger

A small PySide6 tool, launched from a Flame 2026 Python hook, that lets an artist
track time spent on a shot with a live stopwatch and log it as a **TimeLog** in
**Flow Production Tracking (FPT / ShotGrid)**.

- **Trigger:** right-click a **batch group** in the Media Panel → **Time Logger ▸
  Log Time…** (the action is hidden for plain clips).
- **Auth:** reuses the live ShotGrid Toolkit session (`sgtk.get_authenticated_user()`),
  so there is no password prompt. The TimeLog is attributed to that user.
- **Project:** taken straight from the running tk-flame engine context
  (`sgtk.platform.current_engine().context.project`) — the authoritative FPT project for
  the session, with no name matching against the Flame project.
- **Capture:** live Start / Pause / Stop stopwatch; duration auto-fills but is editable.
- **Rounding:** the logged duration is rounded to the **nearest 15 minutes**, shown
  live as *"Will log: N min"* before you submit.
- **Link target:** the TimeLog `entity` is a **Task** on the resolved Shot.
- **Shot matching:** exact match of the batch-group name to `Shot.code` within the
  session project; otherwise pick from a searchable Shot dropdown.

## Layout

```
hooks/flame_time_logger_hook.py   Flame hook (get_media_panel_custom_ui_actions)
flame_time_logger/                the app package
  app.py            launch_dialog(): reuse QApplication, keep dialog alive
  dialog.py         TimeLogDialog: stopwatch + form, async ShotGrid I/O
  stopwatch.py      Stopwatch + round_to_quarter_hour (pure logic)
  fpt.py            FPTClient: sgtk auth, engine-context project, lookups, TimeLog
  flame_context.py  reads batch-group names from the Flame selection
tools/smoke_dialog.py             standalone UI run against a fake client
tests/test_stopwatch.py
```

## Install into Flame

1. Put this repository somewhere Flame can read, e.g. `/opt/flame-time-logger`.
2. Point Flame's hook path at the `hooks/` directory. Either:
   - set `DL_PYTHON_HOOK_PATH=/opt/flame-time-logger/hooks` before launching Flame, or
   - copy/symlink `hooks/flame_time_logger_hook.py` into a project/shared hooks dir.
   The hook adds the repo root to `sys.path` itself, so `flame_time_logger` imports.
3. Launch Flame **through the ShotGrid/Flow integration** so a `sgtk` session exists.
4. Restart Flame (or reload Python hooks). Right-click a batch group to find the action.

There is nothing to configure — auth, user, and project all come from the live tk-flame
ShotGrid Toolkit session.

## Development & verification

These deps are for the dev machine only — **not** for Flame:

```bash
python -m pip install -r requirements-dev.txt
```

1. **Unit tests** (no Flame/SG): `python -m pytest tests/`
2. **Standalone UI smoke test** (needs PySide6): `python tools/smoke_dialog.py` — runs
   the real dialog against a fake client and prints the TimeLog payload it would create.
3. **Syntax check** under Flame-compatible Python 3: `python -m compileall flame_time_logger hooks`
4. **In Flame**: right-click a batch group → *Time Logger ▸ Log Time…*, run the
   stopwatch, submit, and confirm the TimeLog appears in FPT on the expected Task with the
   right user/date and a duration that is a multiple of 15 minutes.

## Notes

- TimeLog `duration` is stored in **minutes** (FPT default).
- If there is no authenticated ShotGrid session, the dialog reports a clear error
  instead of crashing.
