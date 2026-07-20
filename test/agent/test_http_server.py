import asyncio

from httpx import ASGITransport, AsyncClient

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


def test_interference_is_unknown_before_analysis_exists():
    response = request(
        app(), "GET", "/v1/interference", params={"node_name": "node-a"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "version": "v1",
        "node_name": "node-a",
        "reason": "unknown",
        "ttl_seconds": 0,
        "items": [],
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
