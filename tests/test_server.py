"""Lot 32 — running on a server: SQLite under concurrency, the health probe, the scheduler process,
the schedule chosen from the web app, and the first start of a blank data directory."""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pytest

from lucidnews import scheduler
from lucidnews.models import Config
from lucidnews.runs_api import ServerScheduleService
from lucidnews.server_init import initialise
from lucidnews.sqlite_util import connect
from tests.test_auth import Client, start_api
from tests.test_security import open_api

TZ = timezone(timedelta(hours=2))


# SQLite ------------------------------------------------------------------------------------------


def test_databases_open_in_wal_mode_with_a_long_wait(tmp_path) -> None:
    conn = connect(tmp_path / "a.sqlite3")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30_000
    conn.close()


def test_a_reader_is_not_blocked_by_a_writer_in_progress(tmp_path) -> None:
    path = tmp_path / "a.sqlite3"
    writer = connect(path)
    writer.execute("CREATE TABLE t (n INTEGER)")
    writer.execute("INSERT INTO t VALUES (1)")
    writer.commit()
    writer.execute("INSERT INTO t VALUES (2)")  # a write transaction left open, as a pipeline run does
    reader = sqlite3.connect(path, timeout=0.2)  # would raise "database is locked" outside WAL
    assert reader.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1  # the committed state
    writer.commit()
    assert reader.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 2


def test_concurrent_writers_wait_for_each_other_instead_of_failing(tmp_path) -> None:
    path = tmp_path / "a.sqlite3"
    connect(path).execute("CREATE TABLE t (n INTEGER)")
    errors: list[Exception] = []

    def write(offset: int) -> None:
        try:
            conn = connect(path)
            for n in range(40):
                with conn:
                    conn.execute("INSERT INTO t VALUES (?)", (offset + n,))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(i * 100,)) for i in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == [] and connect(path).execute("SELECT COUNT(*) FROM t").fetchone()[0] == 160


# Health ------------------------------------------------------------------------------------------


def test_the_health_probe_needs_no_session_and_says_nothing_else(tmp_path, monkeypatch) -> None:
    _, server = start_api(tmp_path, monkeypatch)  # accounts on: every other route answers 401
    try:
        client = Client(server)
        assert client.request("GET", "/api/editions")[0] == 401
        status, body, response = client.request("GET", "/api/healthz")
        assert (status, body) == (200, {"status": "ok"})
        assert response.getheader("Content-Security-Policy")  # it carries the security headers too
    finally:
        server.shutdown()
        server.server_close()


def test_the_health_probe_fails_when_the_archive_does_not_answer(tmp_path, monkeypatch) -> None:
    ctx, httpd = open_api(tmp_path, monkeypatch)
    try:
        ctx.archive.list_runs = lambda **_: (_ for _ in ()).throw(sqlite3.OperationalError("disk I/O error"))  # type: ignore[method-assign]
        status, body, _ = Client(httpd).request("GET", "/api/healthz")
        assert (status, body) == (503, {"status": "unavailable"})
    finally:
        httpd.shutdown()
        httpd.server_close()


# Scheduler ---------------------------------------------------------------------------------------


def schedule(**values):  # type: ignore[no-untyped-def]
    return {"enabled": True, "hour": 8, "minute": 0, "weekdays": [], **values}


def test_a_slot_fires_once_when_its_time_comes() -> None:
    now = datetime(2026, 10, 18, 8, 0, 20, tzinfo=TZ)
    assert scheduler.due_slot(schedule(), now) == datetime(2026, 10, 18, 8, 0, tzinfo=TZ)
    assert scheduler.due_slot(schedule(), now.replace(hour=7, minute=59)) is None  # yesterday's is too old
    fired = schedule(last_fire=now.isoformat())
    assert scheduler.due_slot(fired, now + timedelta(minutes=30)) is None  # already fired


def test_a_slot_missed_while_the_server_was_down_runs_when_it_returns_but_not_much_later() -> None:
    slot_day = datetime(2026, 10, 18, 8, 0, tzinfo=TZ)
    yesterday = schedule(last_fire=(slot_day - timedelta(days=1)).isoformat())
    assert scheduler.due_slot(yesterday, slot_day + timedelta(hours=5)) == slot_day
    assert scheduler.due_slot(yesterday, slot_day + timedelta(hours=7)) is None


def test_weekdays_and_the_switch_are_respected() -> None:
    sunday = datetime(2026, 10, 18, 8, 5, tzinfo=TZ)  # 18 October 2026 is a Sunday
    assert scheduler.due_slot(schedule(weekdays=[1, 2, 3, 4, 5]), sunday) is None
    assert scheduler.due_slot(schedule(weekdays=[7]), sunday) is not None
    assert scheduler.due_slot(schedule(enabled=False), sunday) is None
    assert scheduler.due_slot({}, sunday) is None
    assert scheduler.due_slot(schedule(hour="eight"), sunday) is None


def test_the_tick_records_the_slot_before_starting_the_run_and_never_overlaps(tmp_path, monkeypatch) -> None:
    started: list[str] = []

    class Process:
        def poll(self):  # type: ignore[no-untyped-def]
            return None  # still running

    def fake_start(data_dir, config_path):  # type: ignore[no-untyped-def]
        assert json.loads((tmp_path / "schedule.json").read_text())["last_fire"]  # written first
        started.append("run")
        return Process()

    monkeypatch.setattr(scheduler, "start_run", fake_start)
    scheduler.save(tmp_path, schedule())
    now = datetime(2026, 10, 18, 8, 0, 30, tzinfo=TZ)

    running = scheduler.tick(tmp_path, None, None, now)
    assert started == ["run"] and running is not None
    scheduler.save(tmp_path, schedule())  # even with the slot due again, a run in progress is left alone
    assert scheduler.tick(tmp_path, None, running, now) is running and started == ["run"]
    assert scheduler.is_alive(tmp_path)


def test_a_stale_heartbeat_means_the_scheduler_is_down(tmp_path) -> None:
    assert not scheduler.is_alive(tmp_path)
    scheduler.touch_heartbeat(tmp_path)
    assert scheduler.is_alive(tmp_path)
    old = datetime.now().timestamp() - scheduler.ALIVE_WITHIN_SECONDS - 5
    os.utime(tmp_path / scheduler.HEARTBEAT_FILE, (old, old))
    assert not scheduler.is_alive(tmp_path)
    assert scheduler.main(["--check", "--data-dir", str(tmp_path)]) == 1


def test_the_scheduler_starts_the_real_pipeline_command(tmp_path, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(scheduler.subprocess, "Popen", lambda command, **kw: calls.append((command, kw["env"])) or object())
    scheduler.start_run(tmp_path, None)
    command, env = calls[0]
    assert command[1:3] == ["-m", "lucidnews.main"] and "--data-dir" in command
    assert env["LUCIDNEWS_RUN_ORIGIN"] == "schedule" and env["LUCIDNEWS_RUN_LOG"].endswith("scheduled.log")


# Schedule from the web app -----------------------------------------------------------------------


def test_the_web_app_sets_and_reads_the_server_schedule(tmp_path) -> None:
    service = ServerScheduleService(tmp_path)
    status, body = service.get()
    assert status == 200 and body["supported"] and not body["enabled"] and not body["loaded"]

    status, body = service.update({"enabled": True, "hour": 7, "minute": 30, "weekdays": [3, 1, 1]})
    assert status == 200 and (body["hour"], body["minute"], body["weekdays"]) == (7, 30, [1, 3])
    assert body["next_run"] and not body["loaded"]  # nobody runs it yet
    scheduler.touch_heartbeat(tmp_path)
    assert service.get()[1]["loaded"]

    # Saving a time must not fire a slot already past today.
    saved = scheduler.load(tmp_path)
    assert scheduler.due_slot(saved, datetime.now().astimezone()) is None

    assert service.update({"enabled": False})[1]["enabled"] is False
    assert service.update({"enabled": True, "hour": 25, "minute": 0})[0] == 422
    assert service.update({"hour": 7})[0] == 422


# First start -------------------------------------------------------------------------------------


def test_a_blank_data_directory_gets_a_closed_configuration_and_an_empty_archive(tmp_path) -> None:
    created = initialise(tmp_path / "data", trusted_proxies=["172.28.0.10"])
    assert created == ["config.json", "archive.sqlite3"]
    config = Config.model_validate(json.loads((tmp_path / "data" / "config.json").read_text()))
    assert config.auth.enabled and not config.auth.allow_signup
    assert config.server.trusted_proxies == ["172.28.0.10"]
    assert (tmp_path / "data" / "archive.sqlite3").stat().st_size > 0


def test_the_first_start_never_overwrites_what_exists(tmp_path) -> None:
    initialise(tmp_path)
    (tmp_path / "config.json").write_text('{"kept": true}')
    assert initialise(tmp_path) == []
    assert json.loads((tmp_path / "config.json").read_text()) == {"kept": True}


def test_a_malformed_proxy_address_stops_the_first_start(tmp_path) -> None:
    with pytest.raises(ValueError):
        initialise(tmp_path, trusted_proxies=["not-an-ip"])
    assert not (tmp_path / "config.json").exists()
