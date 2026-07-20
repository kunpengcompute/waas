from dataclasses import dataclass
from datetime import datetime
from threading import Condition, Lock

from agent_http.models import OnlinePod, OnlinePodsRequest


class NodeConflictError(ValueError):
    """Raised when another node tries to replace the active node snapshot."""


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
