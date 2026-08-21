import importlib
import sys
from types import ModuleType, SimpleNamespace


def load_sample_with_fake_kperf(monkeypatch):
    fake = ModuleType("kperf")
    fake.attrs = []
    fake.closed = []
    fake.PmuTaskType = SimpleNamespace(COUNTING=1)
    fake.EvtAttr = lambda *args: args

    def pmu_attr(**kwargs):
        fake.attrs.append(kwargs)
        return kwargs

    fake.PmuAttr = pmu_attr
    fake.open = lambda task_type, attr: 42
    fake.close = lambda pd: fake.closed.append(pd)
    fake.error = lambda: "fake error"
    monkeypatch.setitem(sys.modules, "kperf", fake)
    sys.modules.pop("sample", None)
    return importlib.import_module("sample"), fake


def test_perf_count_forwards_controller_cgroups_unchanged(monkeypatch):
    sample, fake = load_sample_with_fake_kperf(monkeypatch)

    sample.PerfCount(cgroup_paths=("path-a", "path-b"))

    assert fake.attrs[-1]["cgroupNameList"] == ["path-a", "path-b"]


def test_perf_count_close_releases_descriptor_once(monkeypatch):
    sample, fake = load_sample_with_fake_kperf(monkeypatch)
    counter = sample.PerfCount(cgroup_paths=("path-a",))

    counter.close()
    counter.close()

    assert fake.closed == [42]


def test_get_data_keeps_metrics_separate_by_cgroup(monkeypatch):
    sample, _ = load_sample_with_fake_kperf(monkeypatch)
    counter = sample.PerfCount(cgroup_paths=("path-a", "path-b"))
    counter.results = SimpleNamespace(
        iter=(
            SimpleNamespace(
                cgroupName="path-a",
                cpu=0,
                evt="r0008",
                groupId=1,
                count=10,
                countPercent=100.0,
            ),
            SimpleNamespace(
                cgroupName="path-b",
                cpu=0,
                evt="r0008",
                groupId=1,
                count=20,
                countPercent=100.0,
            ),
        )
    )

    data = counter.get_data()

    assert data["all"]["path-a"][0]["INST_RETIRED"]["count"] == 10
    assert data["all"]["path-b"][0]["INST_RETIRED"]["count"] == 20
