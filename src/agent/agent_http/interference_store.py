from dataclasses import dataclass
from datetime import datetime
from threading import Lock


@dataclass(frozen=True)
class InterferenceResult:
    node_name: str
    reason_codes: tuple[int, ...]
    timestamp: datetime


class InterferenceResultStore:
    def __init__(self):
        self._lock = Lock()
        self._result: InterferenceResult | None = None

    def replace(
        self,
        node_name: str,
        reason_codes: tuple[int, ...],
        timestamp: datetime,
    ) -> InterferenceResult:
        normalized_node_name = node_name.strip()
        if not normalized_node_name:
            raise ValueError("node_name must not be empty")
        if not isinstance(reason_codes, (tuple, list)):
            raise ValueError("reason_codes must be a sequence")
        if any(type(code) is not int or code not in range(7) for code in reason_codes):
            raise ValueError("reason codes must be between 0 and 6")
        normalized_reason_codes = tuple(dict.fromkeys(reason_codes))

        result = InterferenceResult(
            node_name=normalized_node_name,
            reason_codes=normalized_reason_codes,
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
