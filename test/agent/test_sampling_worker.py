from datetime import datetime, timezone
from threading import Event, Thread
from time import sleep

from agent_http.interference_store import InterferenceResultStore
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


def test_sampling_failure_recreates_counter_and_retries():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))

    class FailingCounter(FakeCounter):
        def count(self, interval):
            raise RuntimeError("read failed")

    def factory(paths):
        if not created:
            return FailingCounter(paths, created, sampled)
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

    assert len(created) == 2
    assert created[0].closed


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


def test_counter_close_failure_does_not_stop_target_switch():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))

    class CloseFailingCounter(FakeCounter):
        def close(self):
            self.closed = True
            raise RuntimeError("close failed")

    def factory(paths):
        if not created:
            return CloseFailingCounter(paths, created, sampled)
        return FakeCounter(paths, created, sampled)

    worker = SamplingWorker(
        store, stop, factory, 0, FakeProcessor(), FakeMessenger(), FakeHandler(),
        retry_interval=0.01,
    )
    thread = Thread(target=worker.run)
    thread.start()
    wait_until(lambda: bool(sampled))

    store.replace(request(pods=(pod(path="path-b"),), second=1))
    wait_until(lambda: len(created) == 2 and created[1].paths == ("path-b",))
    stop.set()
    store.close()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert created[0].closed


def test_shutdown_during_sample_skips_downstream_pipeline():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))
    messenger = FakeMessenger()

    class StoppingCounter(FakeCounter):
        def count(self, interval):
            super().count(interval)
            stop.set()

    worker = SamplingWorker(
        store=store,
        stop_event=stop,
        counter_factory=lambda paths: StoppingCounter(paths, created, sampled),
        interval=0,
        processor=FakeProcessor(),
        messenger=messenger,
        handler=FakeHandler(),
        retry_interval=0.01,
    )

    worker.run()

    assert messenger.sent == []
    assert created[0].closed


def test_successful_bmc_cycle_stores_interference_reason():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))
    results = InterferenceResultStore()

    class ReasonMessenger(FakeMessenger):
        def get_interference_reason(self):
            return 3

    worker = SamplingWorker(
        store=store,
        stop_event=stop,
        counter_factory=lambda paths: FakeCounter(paths, created, sampled),
        interval=0,
        processor=FakeProcessor(),
        messenger=ReasonMessenger(),
        handler=FakeHandler(),
        interference_store=results,
        retry_interval=0.01,
    )
    thread = Thread(target=worker.run)
    thread.start()
    wait_until(lambda: results.current("node-a") is not None)
    stop.set()
    store.close()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert results.current("node-a").reason_code == 3


def test_failed_bmc_cycle_does_not_replace_interference_reason():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))
    results = InterferenceResultStore()

    class FailingMessenger(FakeMessenger):
        def send_data(self, payload):
            stop.set()
            raise RuntimeError("BMC failed")

        def get_interference_reason(self):
            raise AssertionError("failed BMC cycle must not produce a reason")

    worker = SamplingWorker(
        store=store,
        stop_event=stop,
        counter_factory=lambda paths: FakeCounter(paths, created, sampled),
        interval=0,
        processor=FakeProcessor(),
        messenger=FailingMessenger(),
        handler=FakeHandler(),
        interference_store=results,
        retry_interval=0.01,
    )

    worker.run()

    assert results.current("node-a") is None
