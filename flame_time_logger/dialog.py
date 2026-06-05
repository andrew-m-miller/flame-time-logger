"""The PySide6 time-logging dialog.

A live stopwatch plus a small form. All ShotGrid I/O runs on a background
thread (``QThreadPool``) so Flame's UI never blocks; results are marshalled back
to the GUI thread via signals.
"""

from __future__ import annotations

import datetime as _dt
import traceback
from typing import Any, Callable, List, Optional

from PySide6 import QtCore, QtWidgets

from .fpt import Entity, FPTClient, task_label
from .flame_context import Context
from .stopwatch import Stopwatch, round_to_quarter_hour

# A factory lets tests/smoke runs inject a fake client.
ClientFactory = Callable[[], FPTClient]


class _WorkerSignals(QtCore.QObject):
    finished = QtCore.Signal(object)
    failed = QtCore.Signal(str)


class _Worker(QtCore.QRunnable):
    """Run a blocking callable off the GUI thread and report back via signals."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = _WorkerSignals()

    @QtCore.Slot()
    def run(self) -> None:  # noqa: D401 - Qt entry point
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception:  # noqa: BLE001 - report any failure to the UI
            self.signals.failed.emit(traceback.format_exc())
        else:
            self.signals.finished.emit(result)


def _format_hms(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


class TimeLogDialog(QtWidgets.QDialog):
    def __init__(
        self,
        context: Context,
        client_factory: ClientFactory = FPTClient,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._client_factory = client_factory
        self._client: Optional[FPTClient] = None
        self._project: Optional[Entity] = None

        self._stopwatch = Stopwatch()
        self._duration_user_edited = False
        self._pool = QtCore.QThreadPool.globalInstance()

        self.setWindowTitle("Log Time")
        self.setMinimumWidth(420)
        self._build_ui()

        # Begin timing immediately and load FPT data in the background.
        self._stopwatch.start()
        self._clock = QtCore.QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._on_tick)
        self._clock.start()
        self._update_running_state()
        self._on_tick()

        self._set_busy(True, "Connecting to Flow Production Tracking…")
        self._run(self._load_initial, on_ok=self._on_initial_loaded)

    # -- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        # Stopwatch readout + transport buttons.
        self._clock_label = QtWidgets.QLabel("00:00:00")
        font = self._clock_label.font()
        font.setPointSize(font.pointSize() + 10)
        self._clock_label.setFont(font)
        self._clock_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._clock_label)

        transport = QtWidgets.QHBoxLayout()
        self._start_btn = QtWidgets.QPushButton("Start")
        self._pause_btn = QtWidgets.QPushButton("Pause")
        self._stop_btn = QtWidgets.QPushButton("Stop")
        self._start_btn.clicked.connect(self._on_start)
        self._pause_btn.clicked.connect(self._on_pause)
        self._stop_btn.clicked.connect(self._on_stop)
        for btn in (self._start_btn, self._pause_btn, self._stop_btn):
            transport.addWidget(btn)
        layout.addLayout(transport)

        form = QtWidgets.QFormLayout()

        self._shot_combo = QtWidgets.QComboBox()
        self._shot_combo.setEditable(True)
        self._shot_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self._shot_combo.completer().setCompletionMode(
            QtWidgets.QCompleter.PopupCompletion
        )
        self._shot_combo.completer().setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._shot_combo.activated.connect(self._on_shot_changed)
        form.addRow("Shot:", self._shot_combo)

        self._task_combo = QtWidgets.QComboBox()
        form.addRow("Task:", self._task_combo)

        self._duration_spin = QtWidgets.QSpinBox()
        self._duration_spin.setRange(0, 24 * 60)
        self._duration_spin.setSuffix(" min")
        self._duration_spin.valueChanged.connect(self._on_duration_changed)
        form.addRow("Duration:", self._duration_spin)

        self._will_log_label = QtWidgets.QLabel("Will log: 0 min")
        form.addRow("", self._will_log_label)

        self._date_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Date:", self._date_edit)

        self._description_edit = QtWidgets.QPlainTextEdit()
        self._description_edit.setFixedHeight(70)
        form.addRow("Description:", self._description_edit)

        layout.addLayout(form)

        self._status_label = QtWidgets.QLabel("")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        buttons = QtWidgets.QDialogButtonBox()
        self._log_btn = buttons.addButton(
            "Log Time", QtWidgets.QDialogButtonBox.AcceptRole
        )
        cancel_btn = buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self._log_btn.clicked.connect(self._on_submit)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    # -- background plumbing ---------------------------------------------

    def _run(
        self,
        fn: Callable[..., Any],
        on_ok: Callable[[Any], None],
        on_err: Optional[Callable[[str], None]] = None,
    ) -> None:
        worker = _Worker(fn)
        worker.signals.finished.connect(on_ok)
        worker.signals.failed.connect(on_err or self._on_worker_error)
        self._pool.start(worker)

    def _load_initial(self) -> dict:
        """Connect, resolve project, auto-match shot, and list shots/tasks."""
        client = self._client_factory()
        from .config import load_config

        cfg = load_config()
        project_name = cfg.fpt_project_name(self._context.project_name)
        project = client.resolve_project(project_name)
        if project is None:
            raise RuntimeError(
                f"Could not resolve FPT project for '{self._context.project_name}'."
            )

        shots = client.list_shots(project)
        matched = client.find_shot(project, self._context.primary_shot_name)
        tasks = client.list_tasks(matched) if matched else []
        return {
            "client": client,
            "project": project,
            "shots": shots,
            "matched": matched,
            "tasks": tasks,
        }

    def _on_initial_loaded(self, data: dict) -> None:
        self._client = data["client"]
        self._project = data["project"]

        self._shot_combo.blockSignals(True)
        self._shot_combo.clear()
        matched = data["matched"]
        matched_index = -1
        for shot in data["shots"]:
            self._shot_combo.addItem(shot["code"], shot)
            if matched and shot["id"] == matched["id"]:
                matched_index = self._shot_combo.count() - 1
        if matched_index >= 0:
            self._shot_combo.setCurrentIndex(matched_index)
        self._shot_combo.blockSignals(False)

        self._populate_tasks(data["tasks"])

        if matched:
            self._set_busy(False, f"Matched shot: {matched['code']}")
        else:
            name = self._context.primary_shot_name or "(none)"
            self._set_busy(False, f"No exact match for '{name}'. Pick a shot.")

    def _populate_tasks(self, tasks: List[Entity]) -> None:
        self._task_combo.clear()
        for task in tasks:
            self._task_combo.addItem(task_label(task), task)
        self._task_combo.setEnabled(bool(tasks))

    # -- stopwatch / form behaviour --------------------------------------

    def _on_tick(self) -> None:
        elapsed = self._stopwatch.elapsed_seconds()
        self._clock_label.setText(_format_hms(elapsed))
        if not self._duration_user_edited:
            self._duration_spin.blockSignals(True)
            self._duration_spin.setValue(int(elapsed // 60))
            self._duration_spin.blockSignals(False)
            self._refresh_will_log()

    def _on_start(self) -> None:
        self._stopwatch.start()
        self._update_running_state()

    def _on_pause(self) -> None:
        self._stopwatch.pause()
        self._update_running_state()

    def _on_stop(self) -> None:
        self._stopwatch.pause()
        # Lock the captured duration into the editable field.
        self._duration_user_edited = True
        self._on_tick_refresh_from_elapsed()
        self._update_running_state()

    def _on_tick_refresh_from_elapsed(self) -> None:
        elapsed = self._stopwatch.elapsed_seconds()
        self._duration_spin.blockSignals(True)
        self._duration_spin.setValue(int(elapsed // 60))
        self._duration_spin.blockSignals(False)
        self._clock_label.setText(_format_hms(elapsed))
        self._refresh_will_log()

    def _update_running_state(self) -> None:
        running = self._stopwatch.is_running
        self._start_btn.setEnabled(not running)
        self._pause_btn.setEnabled(running)

    def _on_duration_changed(self, _value: int) -> None:
        # A manual edit takes over from the live stopwatch sync.
        self._duration_user_edited = True
        self._refresh_will_log()

    def _refresh_will_log(self) -> None:
        rounded = round_to_quarter_hour(self._duration_spin.value())
        self._will_log_label.setText(f"Will log: {rounded} min")

    def _on_shot_changed(self, _index: int) -> None:
        shot = self._shot_combo.currentData()
        if not shot or not self._client:
            return
        self._task_combo.clear()
        self._task_combo.setEnabled(False)
        self._set_busy(True, f"Loading tasks for {shot['code']}…")
        self._run(
            lambda: self._client.list_tasks(shot),
            on_ok=self._on_tasks_loaded,
        )

    def _on_tasks_loaded(self, tasks: List[Entity]) -> None:
        self._populate_tasks(tasks)
        msg = "" if tasks else "No tasks on this shot."
        self._set_busy(False, msg)

    # -- submit ----------------------------------------------------------

    def _on_submit(self) -> None:
        if self._client is None or self._project is None:
            self._set_status("Not connected yet — please wait.")
            return
        task = self._task_combo.currentData()
        if not task:
            self._set_status("Select a Task before logging time.")
            return
        minutes = self._duration_spin.value()
        if round_to_quarter_hour(minutes) <= 0:
            self._set_status("Duration rounds to 0 min — nothing to log.")
            return

        qdate = self._date_edit.date()
        when = _dt.date(qdate.year(), qdate.month(), qdate.day())
        description = self._description_edit.toPlainText().strip()

        self._set_busy(True, "Logging time…")
        self._run(
            lambda: self._client.create_time_log(
                self._project, task, minutes, when, description
            ),
            on_ok=self._on_submitted,
        )

    def _on_submitted(self, result: Entity) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Time Logged",
            f"Logged {round_to_quarter_hour(self._duration_spin.value())} min "
            f"(TimeLog #{result.get('id')}).",
        )
        self.accept()

    # -- status helpers --------------------------------------------------

    def _on_worker_error(self, message: str) -> None:
        # Show only the final line in the status bar; full trace to console.
        print(message)  # noqa: T201 - visible in Flame's console/log
        last = message.strip().splitlines()[-1] if message.strip() else "Error"
        self._set_busy(False, last)
        QtWidgets.QMessageBox.critical(self, "Time Logger error", last)

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._log_btn.setEnabled(not busy)
        self._set_status(message)

    def _set_status(self, message: str) -> None:
        self._status_label.setText(message)
