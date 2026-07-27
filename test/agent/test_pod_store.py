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
    waiter = Thread(
        target=lambda: results.append(
            store.wait_for_change(0, timeout=10)
        )
    )
    waiter.start()

    store.replace(request(pods=(pod(),)))
    waiter.join(timeout=1)

    assert not waiter.is_alive()
    assert results[0].target_revision == 1


def test_wait_for_change_returns_current_snapshot_after_timeout():
    store = PodSnapshotStore()
    current = store.replace(request(pods=(pod(),)))

    result = store.wait_for_change(current.target_revision, timeout=0.01)

    assert result == current


def test_close_wakes_waiter_with_none():
    store = PodSnapshotStore()
    results = []
    waiter = Thread(target=lambda: results.append(store.wait_for_change(0)))
    waiter.start()

    store.close()
    waiter.join(timeout=1)

    assert results == [None]
