from datetime import datetime, timezone

import pytest

from agent_http.interference_store import InterferenceResult, InterferenceResultStore


RESULT_TIME = datetime(2026, 7, 20, 10, 30, tzinfo=timezone.utc)
UPDATED_RESULT_TIME = datetime(2026, 7, 20, 10, 31, tzinfo=timezone.utc)


def test_store_is_initially_empty():
    store = InterferenceResultStore()

    assert store.current("node-a") is None


def test_replace_returns_and_stores_latest_result_for_matching_node():
    store = InterferenceResultStore()

    first = store.replace("node-a", (3,), RESULT_TIME)
    second = store.replace("node-a", (4, 3, 4), UPDATED_RESULT_TIME)

    assert store.current(" node-a ") == InterferenceResult(
        node_name="node-a",
        reason_codes=(4, 3),
        timestamp=UPDATED_RESULT_TIME,
    )
    assert store.current(" node-a ") == second
    assert first == InterferenceResult(
        node_name="node-a",
        reason_codes=(3,),
        timestamp=RESULT_TIME,
    )
    assert store.current("node-b") is None


@pytest.mark.parametrize(
    ("node_name", "reason_codes"),
    [
        ("   ", (3,)),
        ("node-a", (-1,)),
        ("node-a", (7,)),
        ("node-a", (True,)),
        ("node-a", (False,)),
        ("node-a", (1.0,)),
        ("node-a", (6.0,)),
        ("node-a", 3),
    ],
)
def test_invalid_replacement_is_rejected_without_changing_state(
    node_name, reason_codes
):
    store = InterferenceResultStore()
    original = store.replace("node-a", (3,), RESULT_TIME)

    with pytest.raises(ValueError):
        store.replace(node_name, reason_codes, RESULT_TIME)

    assert store.current("node-a") == original
