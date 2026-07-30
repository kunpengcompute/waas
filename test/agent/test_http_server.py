import asyncio
import logging
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from agent_http.interference_store import InterferenceResultStore
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


def request(app, method, path, **kwargs):
    async def send():
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as http:
            return await http.request(method, path, **kwargs)

    return asyncio.run(send())


def app():
    return create_app(PodSnapshotStore())


def app_with_results(results):
    return create_app(PodSnapshotStore(), results)


def test_publish_accepts_controller_snapshot():
    response = request(
        app(), "POST", "/v1/online-pods", json=payload(pods=[pod()])
    )

    assert response.status_code == 200
    assert response.json() == {
        "accepted": True,
        "message": "online pod snapshot accepted",
    }


def test_publish_accepts_empty_snapshot():
    response = request(app(), "POST", "/v1/online-pods", json=payload())

    assert response.status_code == 200
    assert response.json()["accepted"] is True


def test_publish_logs_accepted_snapshot_and_each_pod(caplog):
    caplog.set_level(logging.INFO)

    response = request(
        app(),
        "POST",
        "/v1/online-pods",
        json=payload(
            pods=[
                pod(uid="uid-a", path="kubepods.slice/pod-a.slice"),
                pod(uid="uid-b", path="kubepods.slice/pod-b.slice"),
            ]
        ),
    )

    assert response.status_code == 200
    assert (
        "received online pod snapshot: node=node-a "
        "timestamp=2026-07-20T10:30:00+08:00 pod_count=2 revision=1"
        in caplog.messages
    )
    assert (
        "online pod: namespace=default name=online-a uid=uid-a "
        "cgroup_path=kubepods.slice/pod-a.slice"
        in caplog.messages
    )
    assert (
        "online pod: namespace=default name=online-a uid=uid-b "
        "cgroup_path=kubepods.slice/pod-b.slice"
        in caplog.messages
    )


def test_publish_rejects_unsupported_version():
    response = request(
        app(), "POST", "/v1/online-pods", json=payload(version="v2")
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported version: v2"


def test_publish_rejects_duplicate_uid():
    response = request(
        app(),
        "POST",
        "/v1/online-pods",
        json=payload(pods=[pod(), pod(path="path-b")]),
    )

    assert response.status_code == 400
    assert "duplicate pod uid" in response.json()["detail"]


def test_publish_rejects_conflicting_node():
    application = app()
    assert request(
        application, "POST", "/v1/online-pods", json=payload()
    ).status_code == 200

    response = request(
        application,
        "POST",
        "/v1/online-pods",
        json=payload(node="node-b"),
    )

    assert response.status_code == 409


def test_interference_is_empty_before_analysis_exists():
    response = request(
        app_with_results(InterferenceResultStore()),
        "GET",
        "/v1/interference",
        params={"node_name": "node-a"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "version": "v1",
        "node_name": "node-a",
        "reason_codes": [],
    }


def test_interference_logs_empty_when_analysis_does_not_exist(caplog):
    caplog.set_level(logging.INFO)

    response = request(
        app_with_results(InterferenceResultStore()),
        "GET",
        "/v1/interference",
        params={"node_name": "node-a"},
    )

    assert response.status_code == 200
    assert (
        "return interference result: node=node-a reason_codes=[] "
        "raw_reasons=[] source=no_result"
        in caplog.messages
    )


def test_interference_returns_stored_raw_reason_codes_repeatedly():
    results = InterferenceResultStore()
    results.replace(
        "node-a",
        (3, 1, 4, 2, 0),
        datetime(2026, 7, 22, 10, 30, tzinfo=timezone.utc),
    )
    application = app_with_results(results)

    first = request(
        application,
        "GET",
        "/v1/interference",
        params={"node_name": "node-a"},
    )
    second = request(
        application,
        "GET",
        "/v1/interference",
        params={"node_name": "node-a"},
    )

    assert first.status_code == 200
    assert first.json() == {
        "version": "v1",
        "node_name": "node-a",
        "reason_codes": [3, 1, 4, 2, 0],
    }
    assert second.status_code == 200
    assert second.json() == first.json()


def test_interference_returns_raw_base_reason():
    results = InterferenceResultStore()
    results.replace(
        "node-a",
        (0,),
        datetime(2026, 7, 22, 10, 30, tzinfo=timezone.utc),
    )

    response = request(
        app_with_results(results),
        "GET",
        "/v1/interference",
        params={"node_name": "node-a"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "version": "v1",
        "node_name": "node-a",
        "reason_codes": [0],
    }


def test_interference_logs_stored_reasons(caplog):
    caplog.set_level(logging.INFO)
    results = InterferenceResultStore()
    results.replace(
        "node-a",
        (4, 3),
        datetime(2026, 7, 22, 10, 30, tzinfo=timezone.utc),
    )

    response = request(
        app_with_results(results),
        "GET",
        "/v1/interference",
        params={"node_name": "node-a"},
    )

    assert response.status_code == 200
    assert (
        "return interference result: node=node-a reason_codes=(4, 3) "
        "raw_reasons=['membw', 'l3'] "
        "timestamp=2026-07-22T10:30:00+00:00"
        in caplog.messages
    )


def test_interference_returns_unknown_for_another_node():
    results = InterferenceResultStore()
    results.replace(
        "node-a",
        (3,),
        datetime(2026, 7, 22, 10, 30, tzinfo=timezone.utc),
    )

    response = request(
        app_with_results(results),
        "GET",
        "/v1/interference",
        params={"node_name": "node-b"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "version": "v1",
        "node_name": "node-b",
        "reason_codes": [],
    }


def test_interference_rejects_blank_node_name():
    response = request(
        app(), "GET", "/v1/interference", params={"node_name": "   "}
    )

    assert response.status_code == 422


def test_healthz_reports_process_liveness():
    response = request(app(), "GET", "/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
