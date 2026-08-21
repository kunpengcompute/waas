from datetime import datetime

import pytest
from pydantic import ValidationError

from agent_http import models
from agent_http.models import (
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


def test_empty_interference_response_has_controller_shape():
    response = InterferenceResponse.empty("node-a")

    assert response.model_dump(mode="json") == {
        "version": "v1",
        "node_name": "node-a",
        "reason_codes": [],
    }


@pytest.mark.parametrize(
    ("reason_code", "expected"),
    [
        (0, "base"),
        (1, "compute"),
        (2, "l2"),
        (3, "l3"),
        (4, "membw"),
        (5, "tlb"),
        (6, "frontend"),
        (-1, None),
        (7, None),
    ],
)
def test_raw_reason_name_from_code(reason_code, expected):
    assert models.raw_reason_name_from_code(reason_code) == expected
