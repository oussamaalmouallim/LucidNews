"""The server's scheduler (``lucidnews-scheduler``): starts the pipeline at the chosen times.

A container has no launchd, so one small process does it. The chosen times live in
``<data dir>/schedule.json``, written by the web app (``PUT /api/schedule``) and read here
every loop, so a change applies within seconds and nothing restarts.

- The run is the same command as in a terminal (``python -m lucidnews.main``), started with the
  origin ``schedule``; it appears in the run history like any other and holds ``run_lock``,
  so two runs never overlap whoever started them.
- ``last_fire`` is written *before* the run starts: a crash or a restart never fires a slot twice.
- A slot missed while the process was down still runs, if it is less than ``CATCH_UP`` old
  (the same promise launchd makes when a Mac wakes up).
- ``scheduler.heartbeat`` is touched every loop: the web app and the health check read it to know
  the process is alive.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ._cli import add_data_dir_arguments
from .run_lock import LOG_ENV, ORIGIN_ENV

SCHEDULE_FILE = "schedule.json"
HEARTBEAT_FILE = "scheduler.heartbeat"
LOOP_SECONDS = 15
CATCH_UP = timedelta(hours=6)
ALIVE_WITHIN_SECONDS = 4 * LOOP_SECONDS


def load(data_dir: Path) -> Dict[str, Any]:
    try:
        value = json.loads((Path(data_dir) / SCHEDULE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def save(data_dir: Path, schedule: Dict[str, Any]) -> None:
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".schedule.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(schedule, handle)
    os.replace(tmp, directory / SCHEDULE_FILE)


def latest_slot(hour: int, minute: int, weekdays: List[int], now: datetime) -> Optional[datetime]:
    """The most recent time the schedule should have fired at or before ``now``."""
    for back in range(0, 8):
        candidate = (now - timedelta(days=back)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            continue
        if weekdays and candidate.isoweekday() not in weekdays:
            continue
        return candidate
    return None


def due_slot(schedule: Dict[str, Any], now: datetime) -> Optional[datetime]:
    """The slot to fire now: the latest one, not yet fired, not older than ``CATCH_UP``."""
    if not schedule.get("enabled"):
        return None
    hour, minute = schedule.get("hour"), schedule.get("minute")
    if not isinstance(hour, int) or not isinstance(minute, int):
        return None
    slot = latest_slot(hour, minute, schedule.get("weekdays") or [], now)
    if slot is None or now - slot > CATCH_UP:
        return None
    try:
        last = datetime.fromisoformat(schedule["last_fire"]) if schedule.get("last_fire") else None
    except ValueError:
        last = None
    if last is not None and last.tzinfo is None:
        last = last.astimezone()
    return slot if last is None or last < slot else None


def touch_heartbeat(data_dir: Path) -> None:
    path = Path(data_dir) / HEARTBEAT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def is_alive(data_dir: Path) -> bool:
    try:
        age = time.time() - (Path(data_dir) / HEARTBEAT_FILE).stat().st_mtime
    except OSError:
        return False
    return age <= ALIVE_WITHIN_SECONDS


def start_run(data_dir: Path, config_path: Optional[str]) -> subprocess.Popen:
    log = Path(data_dir).resolve() / "runs" / "scheduled.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "lucidnews.main", "--data-dir", str(Path(data_dir).resolve())]
    if config_path:
        command += ["--config", str(Path(config_path).resolve())]
    env = {**os.environ, ORIGIN_ENV: "schedule", LOG_ENV: str(log), "COLUMNS": "120", "NO_COLOR": "1", "PYTHONUNBUFFERED": "1"}
    with open(log, "ab") as out:
        return subprocess.Popen(command, env=env, stdout=out, stderr=out, stdin=subprocess.DEVNULL)


def tick(data_dir: Path, config_path: Optional[str], running: Optional[subprocess.Popen], now: Optional[datetime] = None) -> Optional[subprocess.Popen]:
    """One pass of the loop. Returns the run now in progress, if any."""
    now = now or datetime.now().astimezone()
    touch_heartbeat(data_dir)
    if running is not None and running.poll() is None:
        return running
    schedule = load(data_dir)
    slot = due_slot(schedule, now)
    if slot is None:
        return None
    save(data_dir, {**schedule, "last_fire": now.isoformat()})  # before the run, so it fires once
    print(f"{now:%Y-%m-%d %H:%M} scheduled run starts (slot {slot:%H:%M})", file=sys.stderr, flush=True)
    return start_run(data_dir, config_path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LucidNews scheduler: starts the pipeline at the times chosen in the web app")
    add_data_dir_arguments(parser)
    parser.add_argument("--check", action="store_true", help="exit 0 if a scheduler is running on this data directory (health check)")
    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir)

    if args.check:
        return 0 if is_alive(data_dir) else 1
    print(f"LucidNews scheduler on {data_dir.resolve()} (schedule: {SCHEDULE_FILE}, every {LOOP_SECONDS}s)", file=sys.stderr, flush=True)
    running: Optional[subprocess.Popen] = None
    try:
        while True:
            running = tick(data_dir, args.config, running)
            time.sleep(LOOP_SECONDS)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
