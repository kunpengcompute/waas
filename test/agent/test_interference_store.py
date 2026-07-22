from datetime import datetime, timezone

import pytest

from agent_http.interference_store import InterferenceResult, InterferenceResultStore


RESULT_TIME = datetime(2026, 7, 20, 10, 30, tzinfo=timezone.utc)


def test_store_is_initially_empty():
    store = InterferenceResultStore()

    assert store.current("node-a") is None


def test_replace_returns_and_stores_latest_result_for_matching_node():
    store = InterferenceResultStore()

    result = store.replace("node-a", 3, RESULT_TIME)

    assert result == InterferenceResult(
        node_name="node-a",
        reason_code=3,
        timestamp=RESULT_TIME,
    )
    assert store.current(" node-a ") == result
    assert store.current("node-b") is None


@pytest.mark.parametrize(
    ("node_name", "reason_code"),
    [
        ("   ", 3),
        ("node-a", -1),
        ("node-a", 7),
    ],
)
def test_invalid_replacement_is_rejected_without_changing_state(
    node_name, reason_code
):
    store = InterferenceResultStore()
    original = store.replace("node-a", 3, RESULT_TIME)

    with pytest.raises(ValueError):
        store.replace(node_name, reason_code, RESULT_TIME)

    assert store.current("node-a") == original
