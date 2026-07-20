import importlib
import sys
from types import ModuleType


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
