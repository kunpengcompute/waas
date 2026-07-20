import logging
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
        handler,
        recorder=None,
        retry_interval: float = 1.0,
    ):
        self.store = store
        self.stop_event = stop_event
        self.counter_factory = counter_factory
        self.interval = interval
        self.processor = processor
        self.messenger = messenger
        self.handler = handler
        self.recorder = recorder
        self.retry_interval = retry_interval

    @staticmethod
    def _close_counter(counter) -> None:
        if counter is not None:
            counter.close()

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

                if self.store.current_revision() != active_revision:
                    continue

                try:
                    if self.recorder is not None:
                        self.recorder.insert(data)
                    payload = self.processor.process(data)
                    self.messenger.send_data(payload)
                    advice = self.messenger.get_advice()
                    if advice:
                        self.handler.apply(advice)
                except Exception:
                    logging.exception("sampling downstream pipeline failed")
        finally:
            self._close_counter(counter)
            if self.recorder is not None:
                self.recorder.close()
