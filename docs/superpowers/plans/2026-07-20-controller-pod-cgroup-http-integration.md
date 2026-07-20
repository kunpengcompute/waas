# Controller Pod Cgroup HTTP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing WAAS Agent sampling loop obtain its Pod cgroup target list from the Controller `v1` HTTP API while preserving the current processing and IPMI/BMC pipeline.

**Architecture:** Run FastAPI/Uvicorn in the main thread and the existing sampling loop in one worker thread. HTTP handlers atomically replace a `PodSnapshotStore`; the worker remains the sole owner of `PerfCount` and rebuilds it only when the normalized `(pod_uid, cgroup_path)` target set changes.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, Uvicorn, pytest, FastAPI TestClient/httpx, threading, existing `kperf` integration.

---

## File Map

| File | Responsibility |
| --- | --- |
| `requirements.txt` | Runtime HTTP dependencies. |
| `requirements-test.txt` | Reproducible HTTP test dependencies. |
| `src/agent/agent_http/__init__.py` | HTTP package boundary. |
| `src/agent/agent_http/models.py` | Strict Pydantic `v1` request/response models. |
| `src/agent/agent_http/store.py` | Immutable snapshots, node binding, target revision, condition-variable coordination. |
| `src/agent/agent_http/server.py` | FastAPI application factory and three routes. |
| `src/agent/sample.py` | Accept dynamic cgroup paths and close the kperf descriptor. |
| `src/agent/sampling_worker.py` | Sole-owner sampling state machine and existing downstream pipeline. |
| `src/agent/main.py` | CLI, dependency composition, worker lifecycle, Uvicorn lifecycle. |
| `test/agent/conftest.py` | Add `src/agent` to the test import path. |
| `test/agent/test_http_models.py` | Pydantic contract tests. |
| `test/agent/test_pod_store.py` | Snapshot/revision/concurrency tests. |
| `test/agent/test_http_server.py` | Controller HTTP contract tests. |
| `test/agent/test_sample_cgroups.py` | Fake-kperf verification of `cgroupNameList` and close. |
| `test/agent/test_sampling_worker.py` | Fake-counter worker state-machine tests. |
| `README.en.md` | Installation, HTTP options, and startup guidance. |

## Task 1: Declare HTTP Dependencies and Define API Models

**Files:**
- Create: `requirements.txt`
- Create: `requirements-test.txt`
- Create: `src/agent/agent_http/__init__.py`
- Create: `src/agent/agent_http/models.py`
- Create: `test/agent/conftest.py`
- Create: `test/agent/test_http_models.py`

- [ ] **Step 1: Write the model contract tests**

Create `test/agent/conftest.py`:

```python
import os
import sys


AGENT_SRC = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../src/agent")
)
if AGENT_SRC not in sys.path:
    sys.path.insert(0, AGENT_SRC)
```

Create `test/agent/test_http_models.py`:

```python
from datetime import datetime

import pytest
from pydantic import ValidationError

from agent_http.models import (
    InterferenceReason,
    InterferenceResponse,
    OnlinePodsRequest,
)


VALID_REQUEST = {
    "version": "v1",
    "node_name": "node-a",
    "timestamp": "2026-07-20T10:30:00.123456789+08:00",
    "pods": [
        {
            "namespace": "default",
            "name": "online-a",
            "uid": "uid-a",
            "cgroup_path": "kubepods.slice/pod-a.slice",
        }
    ],
}


def test_online_pods_request_parses_controller_payload():
    request = OnlinePodsRequest.model_validate(VALID_REQUEST)

    assert request.node_name == "node-a"
    assert isinstance(request.timestamp, datetime)
    assert request.pods[0].cgroup_path == "kubepods.slice/pod-a.slice"


@pytest.mark.parametrize("field", ["node_name", "version"])
def test_online_pods_request_rejects_blank_required_string(field):
    payload = dict(VALID_REQUEST)
    payload[field] = "   "

    with pytest.raises(ValidationError):
        OnlinePodsRequest.model_validate(payload)


def test_online_pods_request_rejects_unknown_fields():
    payload = dict(VALID_REQUEST)
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        OnlinePodsRequest.model_validate(payload)


def test_unknown_interference_response_has_controller_shape():
    response = InterferenceResponse.unknown("node-a")

    assert response.model_dump(mode="json") == {
        "version": "v1",
        "node_name": "node-a",
        "reason": InterferenceReason.UNKNOWN.value,
        "ttl_seconds": 0,
        "items": [],
    }
```

- [ ] **Step 2: Run the tests and verify they fail because the package does not exist**

Run:

```bash
python3 -m pytest -q test/agent/test_http_models.py
```

Expected: collection fails with `ModuleNotFoundError: No module named 'agent_http'`.

- [ ] **Step 3: Add dependency declarations**

Create `requirements.txt`:

```text
fastapi>=0.115,<1
pydantic>=2.8,<3
uvicorn>=0.30,<1
```

Create `requirements-test.txt`:

```text
-r requirements.txt
httpx>=0.27,<1
pytest>=7,<9
```

Install the development/test dependencies:

```bash
python3 -m pip install -r requirements-test.txt
```

- [ ] **Step 4: Implement strict API models**

Create an empty `src/agent/agent_http/__init__.py`.

Create `src/agent/agent_http/models.py`:

```python
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class OnlinePod(StrictModel):
    namespace: str
    name: str
    uid: str = Field(min_length=1)
    cgroup_path: str = Field(min_length=1)


class OnlinePodsRequest(StrictModel):
    version: str = Field(min_length=1)
    node_name: str = Field(min_length=1)
    timestamp: datetime
    pods: tuple[OnlinePod, ...]


class OnlinePodsResponse(StrictModel):
    accepted: bool
    message: str | None = None


class InterferenceReason(str, Enum):
    UNKNOWN = "unknown"
    L3 = "l3"
    MB = "mb"
    CPU = "cpu"


class InterferenceItem(StrictModel):
    pod_uid: str = Field(min_length=1)
    score: float


class InterferenceResponse(StrictModel):
    version: str = "v1"
    node_name: str = Field(min_length=1)
    reason: InterferenceReason
    ttl_seconds: int = Field(ge=0)
    items: tuple[InterferenceItem, ...]

    @classmethod
    def unknown(cls, node_name: str) -> "InterferenceResponse":
        return cls(
            node_name=node_name,
            reason=InterferenceReason.UNKNOWN,
            ttl_seconds=0,
            items=(),
        )
```

- [ ] **Step 5: Run the model tests**

Run:

```bash
python3 -m pytest -q test/agent/test_http_models.py
```

Expected: `5 passed`.

- [ ] **Step 6: Commit the models and dependencies**

```bash
git add requirements.txt requirements-test.txt src/agent/agent_http/__init__.py src/agent/agent_http/models.py test/agent/conftest.py test/agent/test_http_models.py
git commit -m "feat(agent): add controller HTTP data models"
```

## Task 2: Implement the Thread-Safe Pod Snapshot Store

**Files:**
- Create: `src/agent/agent_http/store.py`
- Create: `test/agent/test_pod_store.py`

- [ ] **Step 1: Write failing snapshot and revision tests**

Create `test/agent/test_pod_store.py`:

```python
from datetime import datetime, timezone
from threading import Thread

import pytest

from agent_http.models import OnlinePod, OnlinePodsRequest
from agent_http.store import NodeConflictError, PodSnapshotStore


def request(node="node-a", pods=(), second=0):
    return OnlinePodsRequest(
        version="v1",
        node_name=node,
        timestamp=datetime(2026, 7, 20, 10, 30, second, tzinfo=timezone.utc),
        pods=tuple(pods),
    )


def pod(uid="uid-a", path="kubepods.slice/pod-a.slice", name="online-a"):
    return OnlinePod(
        namespace="default",
        name=name,
        uid=uid,
        cgroup_path=path,
    )


def test_first_empty_snapshot_binds_node_and_advances_revision():
    store = PodSnapshotStore()

    snapshot = store.replace(request())

    assert snapshot.node_name == "node-a"
    assert snapshot.cgroup_paths == ()
    assert snapshot.target_revision == 1


def test_timestamp_and_order_changes_do_not_advance_target_revision():
    store = PodSnapshotStore()
    first = store.replace(request(pods=(pod("uid-a"), pod("uid-b", "path-b"))))
    second = store.replace(
        request(pods=(pod("uid-b", "path-b"), pod("uid-a")), second=1)
    )

    assert first.target_revision == second.target_revision == 1
    assert second.timestamp.second == 1


def test_changed_cgroup_advances_revision_once():
    store = PodSnapshotStore()
    store.replace(request(pods=(pod(),)))

    changed = store.replace(request(pods=(pod(path="path-new"),), second=1))

    assert changed.target_revision == 2
    assert changed.cgroup_paths == ("path-new",)


def test_duplicate_uid_is_rejected_without_replacing_snapshot():
    store = PodSnapshotStore()
    original = store.replace(request(pods=(pod(),)))

    with pytest.raises(ValueError, match="duplicate pod uid"):
        store.replace(request(pods=(pod(), pod(path="path-b")), second=1))

    assert store.current() == original


def test_other_node_is_rejected():
    store = PodSnapshotStore()
    store.replace(request())

    with pytest.raises(NodeConflictError):
        store.replace(request(node="node-b", second=1))


def test_waiter_is_woken_by_changed_snapshot():
    store = PodSnapshotStore()
    results = []
    waiter = Thread(target=lambda: results.append(store.wait_for_change(0)))
    waiter.start()

    store.replace(request(pods=(pod(),)))
    waiter.join(timeout=1)

    assert not waiter.is_alive()
    assert results[0].target_revision == 1


def test_close_wakes_waiter_with_none():
    store = PodSnapshotStore()
    results = []
    waiter = Thread(target=lambda: results.append(store.wait_for_change(0)))
    waiter.start()

    store.close()
    waiter.join(timeout=1)

    assert results == [None]
```

- [ ] **Step 2: Run the store tests and verify the missing module failure**

Run:

```bash
python3 -m pytest -q test/agent/test_pod_store.py
```

Expected: collection fails because `agent_http.store` does not exist.

- [ ] **Step 3: Implement the immutable snapshot store**

Create `src/agent/agent_http/store.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from threading import Condition, Lock

from agent_http.models import OnlinePod, OnlinePodsRequest


class NodeConflictError(ValueError):
    pass


@dataclass(frozen=True)
class PodSnapshot:
    node_name: str
    timestamp: datetime
    pods: tuple[OnlinePod, ...]
    target_revision: int

    @property
    def cgroup_paths(self) -> tuple[str, ...]:
        return tuple(pod.cgroup_path for pod in self.pods)


class PodSnapshotStore:
    def __init__(self):
        self._condition = Condition(Lock())
        self._snapshot: PodSnapshot | None = None
        self._target_key: tuple[tuple[str, str], ...] | None = None
        self._target_revision = 0
        self._closed = False

    def replace(self, request: OnlinePodsRequest) -> PodSnapshot:
        pods_by_uid = {}
        for pod in request.pods:
            if pod.uid in pods_by_uid:
                raise ValueError(f"duplicate pod uid: {pod.uid}")
            pods_by_uid[pod.uid] = pod

        normalized_pods = tuple(pods_by_uid[uid] for uid in sorted(pods_by_uid))
        target_key = tuple((pod.uid, pod.cgroup_path) for pod in normalized_pods)

        with self._condition:
            if self._snapshot is not None and request.node_name != self._snapshot.node_name:
                raise NodeConflictError(
                    f"agent already bound to node {self._snapshot.node_name}"
                )

            if self._target_key is None or target_key != self._target_key:
                self._target_revision += 1
                changed = True
            else:
                changed = False

            snapshot = PodSnapshot(
                node_name=request.node_name,
                timestamp=request.timestamp,
                pods=normalized_pods,
                target_revision=self._target_revision,
            )
            self._snapshot = snapshot
            self._target_key = target_key
            if changed:
                self._condition.notify_all()
            return snapshot

    def current(self) -> PodSnapshot | None:
        with self._condition:
            return self._snapshot

    def current_revision(self) -> int:
        with self._condition:
            return self._target_revision

    def wait_for_change(self, after_revision: int) -> PodSnapshot | None:
        with self._condition:
            self._condition.wait_for(
                lambda: self._closed
                or (
                    self._snapshot is not None
                    and self._snapshot.target_revision != after_revision
                )
            )
            if self._closed:
                return None
            return self._snapshot

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
```

- [ ] **Step 4: Run the store tests**

Run:

```bash
python3 -m pytest -q test/agent/test_pod_store.py
```

Expected: `7 passed`.

- [ ] **Step 5: Commit the snapshot store**

```bash
git add src/agent/agent_http/store.py test/agent/test_pod_store.py
git commit -m "feat(agent): store controller pod snapshots safely"
```

## Task 3: Implement the FastAPI Contract

This task implements the complete first-phase HTTP surface: `POST /v1/online-pods`, `GET /v1/interference`, and `GET /healthz`.

**Files:**
- Create: `src/agent/agent_http/server.py`
- Create: `test/agent/test_http_server.py`

- [ ] **Step 1: Write failing HTTP contract tests**

Create `test/agent/test_http_server.py`:

```python
from fastapi.testclient import TestClient

from agent_http.server import create_app
from agent_http.store import PodSnapshotStore


def payload(node="node-a", pods=None, version="v1"):
    return {
        "version": version,
        "node_name": node,
        "timestamp": "2026-07-20T10:30:00+08:00",
        "pods": [] if pods is None else pods,
    }


def pod(uid="uid-a", path="kubepods.slice/pod-a.slice"):
    return {
        "namespace": "default",
        "name": "online-a",
        "uid": uid,
        "cgroup_path": path,
    }


def client():
    return TestClient(create_app(PodSnapshotStore()))


def test_publish_accepts_controller_snapshot():
    response = client().post("/v1/online-pods", json=payload(pods=[pod()]))

    assert response.status_code == 200
    assert response.json() == {
        "accepted": True,
        "message": "online pod snapshot accepted",
    }


def test_publish_accepts_empty_snapshot():
    response = client().post("/v1/online-pods", json=payload())

    assert response.status_code == 200
    assert response.json()["accepted"] is True


def test_publish_rejects_unsupported_version():
    response = client().post(
        "/v1/online-pods", json=payload(version="v2")
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported version: v2"


def test_publish_rejects_duplicate_uid():
    response = client().post(
        "/v1/online-pods",
        json=payload(pods=[pod(), pod(path="path-b")]),
    )

    assert response.status_code == 400
    assert "duplicate pod uid" in response.json()["detail"]


def test_publish_rejects_conflicting_node():
    http = client()
    assert http.post("/v1/online-pods", json=payload()).status_code == 200

    response = http.post("/v1/online-pods", json=payload(node="node-b"))

    assert response.status_code == 409


def test_interference_is_unknown_before_analysis_exists():
    response = client().get("/v1/interference", params={"node_name": "node-a"})

    assert response.status_code == 200
    assert response.json() == {
        "version": "v1",
        "node_name": "node-a",
        "reason": "unknown",
        "ttl_seconds": 0,
        "items": [],
    }


def test_interference_rejects_blank_node_name():
    response = client().get("/v1/interference", params={"node_name": "   "})

    assert response.status_code == 422


def test_healthz_reports_process_liveness():
    response = client().get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the tests and verify the missing server failure**

Run:

```bash
python3 -m pytest -q test/agent/test_http_server.py
```

Expected: collection fails because `agent_http.server` does not exist.

- [ ] **Step 3: Implement the FastAPI application factory**

Create `src/agent/agent_http/server.py`:

```python
from fastapi import FastAPI, HTTPException, Query

from agent_http.models import (
    InterferenceResponse,
    OnlinePodsRequest,
    OnlinePodsResponse,
)
from agent_http.store import NodeConflictError, PodSnapshotStore


def create_app(store: PodSnapshotStore) -> FastAPI:
    app = FastAPI(title="WAAS Agent", version="v1")

    @app.post("/v1/online-pods", response_model=OnlinePodsResponse)
    def update_online_pods(request: OnlinePodsRequest) -> OnlinePodsResponse:
        if request.version != "v1":
            raise HTTPException(
                status_code=400,
                detail=f"unsupported version: {request.version}",
            )
        try:
            store.replace(request)
        except NodeConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return OnlinePodsResponse(
            accepted=True,
            message="online pod snapshot accepted",
        )

    @app.get("/v1/interference", response_model=InterferenceResponse)
    def get_interference(
        node_name: str = Query(min_length=1),
    ) -> InterferenceResponse:
        normalized_node_name = node_name.strip()
        if not normalized_node_name:
            raise HTTPException(status_code=422, detail="node name must not be empty")
        return InterferenceResponse.unknown(normalized_node_name)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

- [ ] **Step 4: Run the HTTP tests**

Run:

```bash
python3 -m pytest -q test/agent/test_http_server.py
```

Expected: `8 passed`.

- [ ] **Step 5: Run all HTTP/store focused tests**

Run:

```bash
python3 -m pytest -q \
  test/agent/test_http_models.py \
  test/agent/test_pod_store.py \
  test/agent/test_http_server.py
```

Expected: `20 passed`.

- [ ] **Step 6: Commit the HTTP server**

```bash
git add src/agent/agent_http/server.py test/agent/test_http_server.py
git commit -m "feat(agent): receive controller pod snapshots over HTTP"
```

## Task 4: Pass Dynamic Cgroup Targets into `kperf`

**Files:**
- Modify: `src/agent/sample.py:108-203`
- Create: `test/agent/test_sample_cgroups.py`

- [ ] **Step 1: Write a fake-kperf test for target forwarding and close**

Create `test/agent/test_sample_cgroups.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify the constructor mismatch**

Run:

```bash
python3 -m pytest -q test/agent/test_sample_cgroups.py
```

Expected: failure because `PerfCount.__init__()` does not accept `cgroup_paths`.

- [ ] **Step 3: Replace the placeholder with an injected cgroup list**

Change the relevant parts of `src/agent/sample.py` to:

```python
class PerfCount:
    def __init__(self, cgroup_paths=None):
        self.cgroup_paths = list(cgroup_paths or [])
        self.events = []
        self.data = {}
        self.pd = 0
        self.start_time = None
        self.stop_time = None
        self.results = {}
        self.all_group_num0 = 0
        self._init_event()

    def _open_pd(self):
        evt_list = [evt['event'] for evt in self.events]
        evt_attr_list = [
            kperf.EvtAttr(
                evt['group'], 0, evt['excludeUser'], evt['excludeKernel']
            )
            for evt in self.events
        ]
        pmu_attr = kperf.PmuAttr(
            evtList=evt_list,
            cgroupNameList=self.cgroup_paths,
            evtAttr=evt_attr_list,
        )
        pd = kperf.open(kperf.PmuTaskType.COUNTING, pmu_attr)
        if pd == -1:
            raise ValueError(kperf.error())
        return pd

    def close(self):
        if self.pd:
            kperf.close(self.pd)
            self.pd = 0
```

Do not change `count()` or `get_data()` aggregation behavior in this task.

- [ ] **Step 4: Run the fake-kperf tests**

Run:

```bash
python3 -m pytest -q test/agent/test_sample_cgroups.py
```

Expected: `2 passed`.

- [ ] **Step 5: Check Python syntax**

Run:

```bash
python3 -m compileall -q src/agent/sample.py
```

Expected: exit status 0.

- [ ] **Step 6: Commit the dynamic target support**

```bash
git add src/agent/sample.py test/agent/test_sample_cgroups.py
git commit -m "feat(agent): configure PMU collection from pod cgroups"
```

## Task 5: Extract the Single-Owner Sampling Worker

**Files:**
- Create: `src/agent/sampling_worker.py`
- Create: `test/agent/test_sampling_worker.py`

- [ ] **Step 1: Write failing worker state-machine tests**

Create `test/agent/test_sampling_worker.py`:

```python
from datetime import datetime, timezone
from threading import Event, Thread
from time import sleep

from agent_http.models import OnlinePod, OnlinePodsRequest
from agent_http.store import PodSnapshotStore
from sampling_worker import SamplingWorker


def request(pods=(), second=0):
    return OnlinePodsRequest(
        version="v1",
        node_name="node-a",
        timestamp=datetime(2026, 7, 20, 10, 30, second, tzinfo=timezone.utc),
        pods=tuple(pods),
    )


def pod(uid="uid-a", path="path-a"):
    return OnlinePod(
        namespace="default", name="online", uid=uid, cgroup_path=path
    )


class FakeCounter:
    def __init__(self, paths, created, sampled):
        self.paths = tuple(paths)
        self.closed = False
        self._created = created
        self._sampled = sampled
        created.append(self)

    def count(self, interval):
        self._sampled.append(self.paths)
        sleep(0.001)

    def get_data(self):
        return {
            "start_time": None,
            "stop_time": None,
            "all": {},
            "sampled_paths": self.paths,
        }

    def close(self):
        self.closed = True


class FakeProcessor:
    def process(self, data):
        return data


class FakeMessenger:
    def __init__(self):
        self.sent = []

    def send_data(self, payload):
        self.sent.append(payload)

    def get_advice(self):
        return {}


class FakeHandler:
    def apply(self, advice):
        raise AssertionError("empty advice must not be applied")


def build_worker(store, stop, created, sampled):
    return SamplingWorker(
        store=store,
        stop_event=stop,
        counter_factory=lambda paths: FakeCounter(paths, created, sampled),
        interval=0,
        processor=FakeProcessor(),
        messenger=FakeMessenger(),
        handler=FakeHandler(),
        retry_interval=0.01,
    )


def wait_until(predicate, timeout=1):
    for _ in range(100):
        if predicate():
            return
        sleep(timeout / 100)
    raise AssertionError("condition not reached")


def test_worker_waits_for_snapshot_then_passes_paths_to_counter():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    worker = build_worker(store, stop, created, sampled)
    thread = Thread(target=worker.run)
    thread.start()
    assert created == []

    store.replace(request(pods=(pod(),)))
    wait_until(lambda: bool(sampled))
    stop.set()
    store.close()
    thread.join(timeout=1)

    assert created[0].paths == ("path-a",)
    assert created[0].closed


def test_equivalent_snapshot_does_not_recreate_counter():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))
    worker = build_worker(store, stop, created, sampled)
    thread = Thread(target=worker.run)
    thread.start()
    wait_until(lambda: bool(sampled))

    store.replace(request(pods=(pod(),), second=1))
    sleep(0.05)
    stop.set()
    store.close()
    thread.join(timeout=1)

    assert len(created) == 1


def test_changed_and_empty_snapshots_recreate_then_pause():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))
    worker = build_worker(store, stop, created, sampled)
    thread = Thread(target=worker.run)
    thread.start()
    wait_until(lambda: len(created) == 1)

    store.replace(request(pods=(pod(path="path-b"),), second=1))
    wait_until(lambda: len(created) == 2)
    assert created[0].closed
    assert created[1].paths == ("path-b",)

    store.replace(request(pods=(), second=2))
    wait_until(lambda: created[1].closed)
    count_after_empty = len(sampled)
    sleep(0.05)
    stop.set()
    store.close()
    thread.join(timeout=1)

    assert len(sampled) == count_after_empty
```

- [ ] **Step 2: Run the worker tests and verify the missing module failure**

Run:

```bash
python3 -m pytest -q test/agent/test_sampling_worker.py
```

Expected: collection fails because `sampling_worker` does not exist.

- [ ] **Step 3: Implement the worker state machine**

Create `src/agent/sampling_worker.py`:

```python
import logging
from threading import Event
from typing import Callable

from agent_http.store import PodSnapshotStore


class SamplingWorker:
    def __init__(
        self,
        store: PodSnapshotStore,
        stop_event: Event,
        counter_factory: Callable[[tuple[str, ...]], object],
        interval: float,
        processor,
        messenger,
        handler,
        recorder=None,
        retry_interval: float = 1.0,
    ):
        self.store = store
        self.stop_event = stop_event
        self.counter_factory = counter_factory
        self.interval = interval
        self.processor = processor
        self.messenger = messenger
        self.handler = handler
        self.recorder = recorder
        self.retry_interval = retry_interval

    @staticmethod
    def _close_counter(counter) -> None:
        if counter is not None:
            counter.close()

    def run(self) -> None:
        counter = None
        active_revision = 0
        try:
            while not self.stop_event.is_set():
                snapshot = self.store.current()
                if snapshot is None or (
                    counter is None
                    and snapshot.target_revision == active_revision
                    and not snapshot.cgroup_paths
                ):
                    snapshot = self.store.wait_for_change(active_revision)
                    if snapshot is None:
                        return

                if snapshot.target_revision != active_revision:
                    self._close_counter(counter)
                    counter = None
                    if not snapshot.cgroup_paths:
                        active_revision = snapshot.target_revision
                        continue
                    try:
                        counter = self.counter_factory(snapshot.cgroup_paths)
                        active_revision = snapshot.target_revision
                    except Exception:
                        logging.exception("create PerfCount failed")
                        self.stop_event.wait(self.retry_interval)
                        continue

                if counter is None:
                    continue

                try:
                    counter.count(self.interval)
                    data = counter.get_data()
                except Exception:
                    logging.exception("sample pod cgroups failed")
                    self._close_counter(counter)
                    counter = None
                    active_revision = 0
                    self.stop_event.wait(self.retry_interval)
                    continue

                if self.store.current_revision() != active_revision:
                    continue

                try:
                    if self.recorder is not None:
                        self.recorder.insert(data)
                    payload = self.processor.process(data)
                    self.messenger.send_data(payload)
                    advice = self.messenger.get_advice()
                    if advice:
                        self.handler.apply(advice)
                except Exception:
                    logging.exception("sampling downstream pipeline failed")
        finally:
            self._close_counter(counter)
            if self.recorder is not None:
                self.recorder.close()
```

- [ ] **Step 4: Run the worker tests**

Run:

```bash
python3 -m pytest -q test/agent/test_sampling_worker.py
```

Expected: `3 passed` and no live worker threads after the tests.

- [ ] **Step 5: Add failure and stale-sample regression tests**

Append to `test/agent/test_sampling_worker.py`:

```python
def test_counter_creation_failure_is_retried():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))
    attempts = []

    def factory(paths):
        attempts.append(tuple(paths))
        if len(attempts) == 1:
            raise RuntimeError("open failed")
        return FakeCounter(paths, created, sampled)

    worker = SamplingWorker(
        store, stop, factory, 0, FakeProcessor(), FakeMessenger(), FakeHandler(),
        retry_interval=0.01,
    )
    thread = Thread(target=worker.run)
    thread.start()
    wait_until(lambda: bool(sampled))
    stop.set()
    store.close()
    thread.join(timeout=1)

    assert len(attempts) >= 2


def test_sample_from_replaced_snapshot_is_not_forwarded():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))
    messenger = FakeMessenger()

    class ReplacingCounter(FakeCounter):
        def count(self, interval):
            super().count(interval)
            store.replace(request(pods=(pod(path="path-b"),), second=1))

    worker = SamplingWorker(
        store=store,
        stop_event=stop,
        counter_factory=lambda paths: ReplacingCounter(paths, created, sampled),
        interval=0,
        processor=FakeProcessor(),
        messenger=messenger,
        handler=FakeHandler(),
        retry_interval=0.01,
    )
    thread = Thread(target=worker.run)
    thread.start()
    wait_until(lambda: len(created) == 2)
    wait_until(lambda: bool(messenger.sent))
    stop.set()
    store.close()
    thread.join(timeout=1)

    assert all(
        payload["sampled_paths"] != ("path-a",)
        for payload in messenger.sent
    )
```

- [ ] **Step 6: Run all worker tests**

Run:

```bash
python3 -m pytest -q test/agent/test_sampling_worker.py
```

Expected: `5 passed`.

- [ ] **Step 7: Commit the sampling worker**

```bash
git add src/agent/sampling_worker.py test/agent/test_sampling_worker.py
git commit -m "refactor(agent): run sampling from pod snapshot worker"
```

## Task 6: Wire Uvicorn and the Worker into `main.py`

**Files:**
- Modify: `src/agent/main.py:7-121`
- Create: `test/agent/test_main.py`

- [ ] **Step 1: Write failing CLI and composition tests**

Create `test/agent/test_main.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify the missing CLI fields/factory failure**

Run:

```bash
python3 -m pytest -q test/agent/test_main.py
```

Expected: failures for missing `http_host`/`http_port` and `_create_counter`.

- [ ] **Step 3: Refactor `main.py` into composition and lifecycle code**

Keep `_get_interval()` and existing processor/messenger/handler construction. Remove startup-time counter creation and the inline `while True` loop. Add these imports and helpers:

```python
import threading

import uvicorn

from agent_http.server import create_app
from agent_http.store import PodSnapshotStore
from sampling_worker import SamplingWorker


def _create_counter(cgroup_paths):
    return PerfCount(cgroup_paths=cgroup_paths)
```

Add to `_get_args()`:

```python
parser.add_argument(
    "--http-host", default="127.0.0.1",
    help="HTTP listen host, default 127.0.0.1",
)
parser.add_argument(
    "--http-port", type=int, default=18080,
    help="HTTP listen port, default 18080",
)
```

Replace `main()` with:

```python
def main():
    args = _get_args()
    interval = _get_interval(args.interval)

    processor = DataProcessor()
    processor.add_porcesser("numa_reduction", [NumaReduction()])

    messenger = Messenger()
    handler = Handler()
    handler.add_handler(util.Weapon.CORE.value, CoreHandler())
    handler.add_handler(util.Weapon.SOC.value, SocHandler())

    recorder = None
    if args.output:
        recorder = DataRecorder(args.output, args.maxrows)

    store = PodSnapshotStore()
    stop_event = threading.Event()
    worker = SamplingWorker(
        store=store,
        stop_event=stop_event,
        counter_factory=_create_counter,
        interval=interval,
        processor=processor,
        messenger=messenger,
        handler=handler,
        recorder=recorder,
    )
    worker_thread = threading.Thread(
        target=worker.run,
        name="waas-sampling-worker",
    )
    worker_thread.start()

    try:
        config = uvicorn.Config(
            create_app(store),
            host=args.http_host,
            port=args.http_port,
            log_level="info",
        )
        uvicorn.Server(config).run()
    finally:
        stop_event.set()
        store.close()
        worker_thread.join()
```

Remove the no-longer-used `psutil` import, `_get_cpus()` helper, and `--cpus` argument because sampling targets now come exclusively from Controller snapshots.

- [ ] **Step 4: Run main composition tests**

Run:

```bash
python3 -m pytest -q test/agent/test_main.py
```

Expected: `2 passed`.

- [ ] **Step 5: Run syntax and focused tests**

Run:

```bash
python3 -m compileall -q src/agent
python3 -m pytest -q \
  test/agent/test_http_models.py \
  test/agent/test_pod_store.py \
  test/agent/test_http_server.py \
  test/agent/test_sample_cgroups.py \
  test/agent/test_sampling_worker.py \
  test/agent/test_main.py
```

Expected: compileall exits 0 and all focused tests pass.

- [ ] **Step 6: Commit the process integration**

```bash
git add src/agent/main.py test/agent/test_main.py
git commit -m "feat(agent): drive sampling through controller HTTP snapshots"
```

## Task 7: Document Operation and Run Final Verification

**Files:**
- Modify: `README.en.md:1-52`

- [ ] **Step 1: Add dependency and HTTP startup documentation**

Add these instructions to `README.en.md`, correcting the existing Windows-style path separators while touching the file:

````markdown
## Agent HTTP integration

Install Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Start WAAS Agent. The HTTP service listens on loopback port 18080 by default and sampling remains idle until the controller publishes an online Pod snapshot:

```bash
python3 src/agent/main.py \
  --http-host 127.0.0.1 \
  --http-port 18080 \
  --interval 1
```

The controller should use:

```text
--dynamic-agent-addr=http://127.0.0.1:18080
```

`POST /v1/online-pods` replaces the complete sampling target list. An empty Pod list pauses PMU collection. `GET /v1/interference` returns `unknown` until interference analysis is implemented.
````

- [ ] **Step 2: Run documentation and whitespace checks**

Run:

```bash
git diff --check
rg -n "src\\\\prf" README.en.md
```

Expected: `git diff --check` exits 0; `rg` finds no Windows-style `src\prf` path.

- [ ] **Step 3: Run the complete focused verification suite**

Run:

```bash
python3 -m compileall -q src/agent
python3 -m pytest -q \
  test/agent/test_http_models.py \
  test/agent/test_pod_store.py \
  test/agent/test_http_server.py \
  test/agent/test_sample_cgroups.py \
  test/agent/test_sampling_worker.py \
  test/agent/test_main.py
```

Expected: syntax check exits 0 and every focused test passes without a real `kperf` installation.

- [ ] **Step 4: Run the Controller-side protocol tests**

From `/home/yanxiang/Desktop/cloud-native` run:

```bash
go test ./pkg/kunpeng-qos-controller/dynamiccontrol/...
```

Expected: all dynamic-control protocol tests pass. This verifies that no Controller contract assumption changed while implementing the Agent peer.

- [ ] **Step 5: Perform a local HTTP smoke test**

Run the Agent with a fake/stub `kperf` only in a test environment, or run it on the target Kunpeng host. Publish a snapshot:

```bash
curl --fail-with-body \
  -X POST http://127.0.0.1:18080/v1/online-pods \
  -H 'Content-Type: application/json' \
  -d '{
    "version":"v1",
    "node_name":"node-a",
    "timestamp":"2026-07-20T10:30:00+08:00",
    "pods":[{
      "namespace":"default",
      "name":"online-a",
      "uid":"uid-a",
      "cgroup_path":"kubepods.slice/pod-a.slice"
    }]
  }'
```

Expected response:

```json
{"accepted":true,"message":"online pod snapshot accepted"}
```

Query the placeholder result:

```bash
curl --fail-with-body \
  'http://127.0.0.1:18080/v1/interference?node_name=node-a'
```

Expected JSON contains `"reason":"unknown"`, `"ttl_seconds":0`, and `"items":[]`.

- [ ] **Step 6: Commit documentation**

```bash
git add README.en.md
git commit -m "docs(agent): document controller-driven pod sampling"
```

- [ ] **Step 7: Inspect final branch state**

Run:

```bash
git status --short --branch
git log --oneline --decorate -8
```

Expected: only the previously untracked architecture diagram files remain outside the implementation commits; the feature changes are committed as the task-specific commits above.

## Target-Host Integration Check

After the focused suite passes, verify on a Kunpeng host with the real `kperf` module and real Pod cgroups:

1. Start the Agent and confirm `/healthz` responds while no snapshot exists.
2. POST two real Pod cgroup paths from Controller.
3. Confirm the value passed to `kperf.PmuAttr(cgroupNameList=...)` contains exactly those two paths.
4. Repeat the same snapshot with a new timestamp and confirm the PMU descriptor is not reopened.
5. Remove one Pod from the snapshot and confirm the descriptor is rebuilt once.
6. POST an empty Pod list and confirm PMU sampling pauses without terminating HTTP.
7. Stop the Agent and confirm the worker and PMU descriptor close cleanly.
