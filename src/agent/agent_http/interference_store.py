from dataclasses import dataclass
from datetime import datetime
from threading import Lock


@dataclass(frozen=True)
class InterferenceResult:
    node_name: str
    reason_code: int
    timestamp: datetime


class InterferenceResultStore:
    def __init__(self):
        self._lock = Lock()
        self._result: InterferenceResult | None = None

    def replace(
        self, node_name: str, reason_code: int, timestamp: datetime
    ) -> InterferenceResult:
        normalized_node_name = node_name.strip()
        if not normalized_node_name:
            raise ValueError("node_name must not be empty")
        if type(reason_code) is not int or reason_code not in range(7):
            raise ValueError("reason_code must be between 0 and 6")

        result = InterferenceResult(
            node_name=normalized_node_name,
            reason_code=reason_code,
            timestamp=timestamp,
        )
        with self._lock:
            self._result = result
            return result

    def current(self, node_name: str) -> InterferenceResult | None:
        normalized_node_name = node_name.strip()
        with self._lock:
            if self._result is None or self._result.node_name != normalized_node_name:
                return None
            return self._result
