import logging
from datetime import datetime, timezone
from threading import Event
from typing import Callable

from agent_http.store import PodSnapshotStore


class SamplingWorker:
    def __init__(
        self,
        store: PodSnapshotStore,
        stop_event: Event,
        counter_factory: Callable[[tuple[str, ...]], object],
        interval: float,
        processor,
        messenger,
        recorder=None,
        retry_interval: float = 1.0,
        interference_store=None,
    ):
        self.store = store
        self.stop_event = stop_event
        self.counter_factory = counter_factory
        self.interval = interval
        self.processor = processor
        self.messenger = messenger
        self.recorder = recorder
        self.retry_interval = retry_interval
        self.interference_store = interference_store

    @staticmethod
    def _close_counter(counter) -> None:
        if counter is not None:
            try:
                counter.close()
            except Exception:
                logging.exception("close PerfCount failed")

    def run(self) -> None:
        counter = None
        active_revision = 0
        try:
            while not self.stop_event.is_set():
                snapshot = self.store.current()
                if snapshot is None or (
                    counter is None
                    and snapshot.target_revision == active_revision
                    and not snapshot.cgroup_paths
                ):
                    snapshot = self.store.wait_for_change(active_revision)
                    if snapshot is None:
                        return

                if snapshot.target_revision != active_revision:
                    self._close_counter(counter)
                    counter = None
                    if not snapshot.cgroup_paths:
                        active_revision = snapshot.target_revision
                        continue
                    try:
                        counter = self.counter_factory(snapshot.cgroup_paths)
                        active_revision = snapshot.target_revision
                    except Exception:
                        logging.exception("create PerfCount failed")
                        self.stop_event.wait(self.retry_interval)
                        continue

                if counter is None:
                    continue

                try:
                    counter.count(self.interval)
                    data = counter.get_data()
                except Exception:
                    logging.exception("sample pod cgroups failed")
                    self._close_counter(counter)
                    counter = None
                    active_revision = 0
                    self.stop_event.wait(self.retry_interval)
                    continue

                if self.stop_event.is_set():
                    return

                if self.store.current_revision() != active_revision:
                    continue

                try:
                    reason_codes = []
                    for cgroup_path, cgroup_metrics in data.get("all", {}).items():
                        if self.stop_event.is_set():
                            return
                        if self.store.current_revision() != active_revision:
                            break
                        cgroup_data = {
                            "start_time": data["start_time"],
                            "stop_time": data["stop_time"],
                            "cgroup_path": cgroup_path,
                            "all": cgroup_metrics,
                        }
                        if self.recorder is not None:
                            try:
                                self.recorder.insert(cgroup_data)
                            except Exception:
                                logging.exception(
                                    "record cgroup metrics failed: cgroup_path=%s",
                                    cgroup_path,
                                )
                        try:
                            payload = self.processor.process(cgroup_data)
                            self.messenger.send_data(payload)
                            self.messenger.get_advice()
                            if self.interference_store is not None:
                                reason_codes.append(
                                    self.messenger.get_interference_reason()
                                )
                        except Exception:
                            logging.exception(
                                "cgroup analysis failed: cgroup_path=%s",
                                cgroup_path,
                            )

                    if self.stop_event.is_set():
                        return
                    if self.store.current_revision() != active_revision:
                        continue
                    if self.interference_store is not None:
                        self.interference_store.replace(
                            snapshot.node_name,
                            tuple(reason_codes),
                            datetime.now(timezone.utc),
                        )
                except Exception:
                    logging.exception("sampling downstream pipeline failed")
        finally:
            self._close_counter(counter)
            if self.recorder is not None:
                self.recorder.close()
