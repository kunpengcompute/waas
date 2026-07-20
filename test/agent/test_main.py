import importlib
import sys
from threading import Event, current_thread
from types import ModuleType

import pytest


def load_main(monkeypatch):
    fake_kperf = ModuleType("kperf")
    fake_psutil = ModuleType("psutil")
    fake_psutil.cpu_count = lambda logical=True: 1
    monkeypatch.setitem(sys.modules, "kperf", fake_kperf)
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    sys.modules.pop("main", None)
    return importlib.import_module("main")


def test_http_cli_defaults(monkeypatch):
    main = load_main(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["waasagent"])

    args = main._get_args()

    assert args.http_host == "127.0.0.1"
    assert args.http_port == 18080


def test_counter_factory_passes_snapshot_paths(monkeypatch):
    main = load_main(monkeypatch)
    captured = []

    class FakePerfCount:
        def __init__(self, cgroup_paths):
            captured.append(tuple(cgroup_paths))

    monkeypatch.setattr(main, "PerfCount", FakePerfCount)

    main._create_counter(("path-a", "path-b"))

    assert captured == [("path-a", "path-b")]


def test_run_agent_runs_sampling_on_caller_thread_and_cleans_up(monkeypatch):
    main = load_main(monkeypatch)
    calls = []

    class FakeWorker:
        def run(self):
            calls.append(("worker", current_thread()))

    class FakeHttpRunner:
        def start(self):
            calls.append(("http-start", current_thread()))

        def stop(self):
            calls.append(("http-stop", current_thread()))

    class FakeStore:
        def close(self):
            calls.append(("store-close", current_thread()))

    stop_event = Event()
    caller_thread = current_thread()

    main._run_agent(FakeWorker(), FakeHttpRunner(), FakeStore(), stop_event)

    assert calls == [
        ("http-start", caller_thread),
        ("worker", caller_thread),
        ("store-close", caller_thread),
        ("http-stop", caller_thread),
    ]
    assert stop_event.is_set()


def test_run_agent_does_not_start_sampling_when_http_start_fails(monkeypatch):
    main = load_main(monkeypatch)
    worker_called = False

    class FakeWorker:
        def run(self):
            nonlocal worker_called
            worker_called = True

    class FakeHttpRunner:
        def start(self):
            raise RuntimeError("HTTP failed")

        def stop(self):
            pass

    class FakeStore:
        def close(self):
            pass

    with pytest.raises(RuntimeError, match="HTTP failed"):
        main._run_agent(FakeWorker(), FakeHttpRunner(), FakeStore(), Event())

    assert not worker_called
