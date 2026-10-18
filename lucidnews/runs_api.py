"""Start the pipeline from the web app and schedule it (local API routes only).

**Runs**: the pipeline runs in a separate process, the same command as in a
terminal (``python -m lucidnews.main``), so it produces the same edition. It writes its
output to ``<data dir>/runs/``; the web app reads the end of that log, with ANSI
codes and every known key value removed, and the current step. One run at a
time: the pipeline holds ``run_lock`` for its whole duration, whoever started it.

**Schedule** (macOS): a launchd agent in ``~/Library/LaunchAgents`` runs the same
command at the chosen times. It holds no secret: keys stay in the project's
``.env``, which the pipeline loads itself. If the Mac sleeps at that time, launchd
runs it when the Mac wakes.
"""

import os
import plistlib
import re
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .run_lock import LOG_ENV, ORIGIN_ENV, current_holder

Response = tuple[int, Dict[str, Any]]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALREADY_RUNNING = 75  # exit code of lucidnews.main when another run holds the lock
LOG_LINES = 40
MIN_SECRET_LENGTH = 6
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# Pipeline output -> step reached (the last match wins).
STEPS = ("fetch", "analyze", "select", "write", "done")
# Real output only: numbers are required, so the source code quoted in a traceback
# ("Analyzed {len(analyzed_items)} items with AI") never counts as a step.
STEP_MARKERS = (
    (re.compile(r"Fetching content since: \d"), "fetch"),
    (re.compile(r"Fetched \d+ items from all sources"), "analyze"),
    (re.compile(r"Analyzed \d+ items with AI"), "select"),
    (re.compile(r"Selected \d+ items with profile filters"), "select"),
    (re.compile(r"Saved [A-Z]{2} summary to"), "write"),
    (re.compile(r"No new content found"), "done"),
    (re.compile(r"LucidNews completed successfully"), "done"),
)


def clean_log(text: str, secrets: Sequence[str]) -> str:
    """Log text safe to show: no colour codes, no carriage returns, no key value."""
    text = ANSI.sub("", text).replace("\r", "")
    for value in secrets:
        if len(value) >= MIN_SECRET_LENGTH:
            text = text.replace(value, "•••")
    return text


def detect_step(text: str) -> Optional[str]:
    step = None
    for line in text.splitlines():
        for marker, name in STEP_MARKERS:
            if marker.search(line):
                step = name
    return step


def _tail(path: Optional[str], lines: int = LOG_LINES, max_bytes: int = 256 * 1024) -> str:
    if not path or not Path(path).is_file():
        return ""
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes))
        text = handle.read().decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def _run_section(log_path: Optional[str]) -> str:
    """The part of a log written by the latest run (the scheduled log is appended to)."""
    lines = _tail(log_path, lines=2000).splitlines()
    starts = [index for index, line in enumerate(lines) if ANSI.sub("", line).strip() == "LucidNews"]  # banner
    return "\n".join(lines[starts[-1]:] if starts else lines)


@dataclass
class RunService:
    data_dir: Path
    config_path: Optional[str] = None
    project_root: Path = PROJECT_ROOT
    # Values to hide from logs (API keys and other secrets the configuration uses).
    secret_values: Callable[[], List[str]] = list
    # The pipeline command; replaced in tests.
    command: Optional[List[str]] = None

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._process: Optional[subprocess.Popen] = None
        self._last: Optional[Dict[str, Any]] = None

    def pipeline_command(self) -> List[str]:
        if self.command is not None:
            return list(self.command)
        command = [sys.executable, "-m", "lucidnews.main", "--data-dir", str(Path(self.data_dir).resolve())]
        if self.config_path:
            command += ["--config", str(Path(self.config_path).resolve())]
        return command

    def _running_here(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> Response:
        with self._lock:
            if self._running_here() or current_holder(self.data_dir):
                return HTTPStatus.CONFLICT, {"error": "a run is already in progress", **self.current()[1]}
            logs = Path(self.data_dir) / "runs"
            logs.mkdir(parents=True, exist_ok=True)
            started = datetime.now(timezone.utc)
            log_path = logs / f"web-{started:%Y%m%dT%H%M%SZ}.log"
            env = {**os.environ, ORIGIN_ENV: "web", LOG_ENV: str(log_path), "COLUMNS": "120", "NO_COLOR": "1", "PYTHONUNBUFFERED": "1"}
            with open(log_path, "wb") as log:
                self._process = subprocess.Popen(
                    self.pipeline_command(),
                    cwd=self.project_root,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=env,
                    start_new_session=True,  # survives a browser tab closing; not killed with the API's terminal
                )
            self._last = {"origin": "web", "started_at": started.isoformat(timespec="seconds"), "log": str(log_path)}
        return HTTPStatus.ACCEPTED, self.current()[1]

    def current(self) -> Response:
        holder = current_holder(self.data_dir)
        running = bool(holder) or self._running_here()
        if holder:
            info = {"origin": holder.get("origin"), "started_at": holder.get("started_at"), "log": holder.get("log")}
        else:
            info = dict(self._last or {})
        exit_code = None
        if not running and self._process is not None and info.get("origin") == "web":
            exit_code = self._process.returncode
        text = clean_log(_run_section(info.get("log")), self.secret_values())
        return HTTPStatus.OK, {
            "running": running,
            "origin": info.get("origin"),
            "started_at": info.get("started_at"),
            "step": detect_step(text),
            "steps": list(STEPS),
            "exit_code": exit_code,
            "already_running": exit_code == ALREADY_RUNNING,
            "log": "\n".join(text.splitlines()[-LOG_LINES:]),
        }


# Schedule ------------------------------------------------------------------------------

LABEL = "com.lucidnews.pipeline"


def _launchctl(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, timeout=15)


@dataclass
class ScheduleService:
    data_dir: Path
    config_path: Optional[str] = None
    project_root: Path = PROJECT_ROOT
    agents_dir: Path = field(default_factory=lambda: Path.home() / "Library" / "LaunchAgents")
    label: str = LABEL
    launchctl: Callable[[List[str]], subprocess.CompletedProcess] = _launchctl
    platform: str = sys.platform
    python: str = sys.executable

    @property
    def plist_path(self) -> Path:
        return self.agents_dir / f"{self.label}.plist"

    @property
    def log_path(self) -> Path:
        return Path(self.data_dir).resolve() / "runs" / "scheduled.log"

    def _domain(self) -> str:
        return f"gui/{os.getuid()}"

    def get(self) -> Response:
        if self.platform != "darwin":
            return HTTPStatus.OK, {"supported": False, "enabled": False}
        enabled = self.plist_path.is_file()
        hour = minute = None
        weekdays: List[int] = []
        if enabled:
            try:
                plist = plistlib.loads(self.plist_path.read_bytes())
                intervals = plist.get("StartCalendarInterval") or []
                intervals = intervals if isinstance(intervals, list) else [intervals]
                if intervals:
                    hour, minute = intervals[0].get("Hour"), intervals[0].get("Minute")
                    weekdays = sorted({7 if entry["Weekday"] == 0 else entry["Weekday"] for entry in intervals if "Weekday" in entry})
            except (plistlib.InvalidFileException, ValueError, AttributeError, KeyError):
                return HTTPStatus.OK, {"supported": True, "enabled": True, "valid": False, "label": self.label}
        loaded = enabled and self.launchctl(["print", f"{self._domain()}/{self.label}"]).returncode == 0
        return HTTPStatus.OK, {
            "supported": True,
            "enabled": enabled,
            "valid": True,
            "loaded": loaded,
            "hour": hour,
            "minute": minute,
            "weekdays": weekdays,
            "next_run": next_run(hour, minute, weekdays) if enabled and hour is not None else None,
            "label": self.label,
            "log": str(self.log_path),
        }

    def update(self, body: Dict[str, Any]) -> Response:
        if self.platform != "darwin":
            return HTTPStatus.NOT_IMPLEMENTED, {"error": "scheduling uses launchd and needs macOS"}
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid schedule", "fields": {"enabled": "must be true or false"}}
        if not enabled:
            self._unload()
            self.plist_path.unlink(missing_ok=True)
            return self.get()
        hour, minute, weekdays = body.get("hour"), body.get("minute"), body.get("weekdays", [])
        fields = schedule_field_errors(hour, minute, weekdays)
        if fields:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid schedule", "fields": fields}
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        data = plistlib.dumps(self.plist(hour, minute, sorted(set(weekdays))))
        fd, tmp = tempfile.mkstemp(dir=self.agents_dir, prefix=f".{self.label}.", suffix=".tmp")
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, self.plist_path)
        self._unload()  # the new times apply only once the agent is loaded again
        result = self.launchctl(["bootstrap", self._domain(), str(self.plist_path)])
        if result.returncode != 0:
            self.plist_path.unlink(missing_ok=True)
            message = (result.stderr or result.stdout or "").strip().splitlines()
            return HTTPStatus.BAD_GATEWAY, {"error": "launchd refused the schedule", "detail": message[0][:200] if message else None}
        return self.get()

    def _unload(self) -> None:
        self.launchctl(["bootout", f"{self._domain()}/{self.label}"])  # fails harmlessly when not loaded

    def plist(self, hour: int, minute: int, weekdays: List[int]) -> Dict[str, Any]:
        command = [self.python, "-m", "lucidnews.main", "--data-dir", str(Path(self.data_dir).resolve())]
        if self.config_path:
            command += ["--config", str(Path(self.config_path).resolve())]
        intervals = [{"Hour": hour, "Minute": minute, "Weekday": day} for day in weekdays] or [{"Hour": hour, "Minute": minute}]
        return {
            "Label": self.label,
            "ProgramArguments": command,
            "WorkingDirectory": str(Path(self.project_root).resolve()),
            "EnvironmentVariables": {
                ORIGIN_ENV: "schedule",
                LOG_ENV: str(self.log_path),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "COLUMNS": "120",
                "NO_COLOR": "1",
                "PYTHONUNBUFFERED": "1",
            },
            "StartCalendarInterval": intervals,
            "StandardOutPath": str(self.log_path),
            "StandardErrorPath": str(self.log_path),
            "RunAtLoad": False,
        }


def schedule_field_errors(hour: Any, minute: Any, weekdays: Any) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
        fields["hour"] = "must be between 0 and 23"
    if isinstance(minute, bool) or not isinstance(minute, int) or not 0 <= minute <= 59:
        fields["minute"] = "must be between 0 and 59"
    if not isinstance(weekdays, list) or any(isinstance(day, bool) or not isinstance(day, int) or not 1 <= day <= 7 for day in weekdays):
        fields["weekdays"] = "days from 1 (Monday) to 7 (Sunday); empty for every day"
    return fields


@dataclass
class ServerScheduleService:
    """The schedule of a server: kept in ``<data dir>/schedule.json`` and run by the
    ``lucidnews-scheduler`` process (see ``scheduler``), since a container has no launchd."""

    data_dir: Path

    def get(self) -> Response:
        from . import scheduler

        schedule = scheduler.load(self.data_dir)
        enabled = bool(schedule.get("enabled"))
        hour, minute, weekdays = schedule.get("hour"), schedule.get("minute"), schedule.get("weekdays") or []
        return HTTPStatus.OK, {
            "supported": True,
            "enabled": enabled,
            "valid": True,
            "loaded": enabled and scheduler.is_alive(self.data_dir),  # the process that runs it is up
            "hour": hour if enabled else None,
            "minute": minute if enabled else None,
            "weekdays": weekdays if enabled else [],
            "next_run": next_run(hour, minute, weekdays) if enabled and hour is not None else None,
            "label": "server",
            "log": str(Path(self.data_dir).resolve() / "runs" / "scheduled.log"),
        }

    def update(self, body: Dict[str, Any]) -> Response:
        from . import scheduler

        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid schedule", "fields": {"enabled": "must be true or false"}}
        schedule = scheduler.load(self.data_dir)
        if not enabled:
            scheduler.save(self.data_dir, {**schedule, "enabled": False})
            return self.get()
        hour, minute, weekdays = body.get("hour"), body.get("minute"), body.get("weekdays", [])
        fields = schedule_field_errors(hour, minute, weekdays)
        if fields:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid schedule", "fields": fields}
        # A new time starts clean: a slot already past today must not fire at once.
        scheduler.save(
            self.data_dir,
            {"enabled": True, "hour": hour, "minute": minute, "weekdays": sorted(set(weekdays)), "last_fire": datetime.now().astimezone().isoformat()},
        )
        return self.get()


def next_run(hour: int, minute: int, weekdays: Sequence[int], now: Optional[datetime] = None) -> str:
    """Next local time the schedule fires (ISO 8601 with offset)."""
    now = now or datetime.now().astimezone()
    for offset in range(0, 8):
        day = now + timedelta(days=offset)
        candidate = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            continue
        if weekdays and candidate.isoweekday() not in weekdays:
            continue
        return candidate.isoformat(timespec="minutes")
    raise ValueError("no next run")  # unreachable: a week always holds one
