from threading import Event

import pytest

from agent_http.store import PodSnapshotStore
from http_server_runner import HttpServerRunner, HttpServerStartupError


class FakeServer:
    def __init__(self):
        self.started = False
        self.should_exit = False

    def run(self):
        self.started = True
        while not self.should_exit:
            Event().wait(0.001)


class FailingServer(FakeServer):
    def run(self):
        raise OSError("address already in use")


class UnexpectedExitServer(FakeServer):
    def run(self):
        self.started = True


def test_start_waits_until_server_is_ready_and_stop_joins_thread():
    server = FakeServer()
    runner = HttpServerRunner(
        server=server,
        store=PodSnapshotStore(),
        stop_event=Event(),
        startup_timeout=0.2,
    )

    runner.start()
    assert server.started
    assert runner.is_alive()

    runner.stop()
    assert server.should_exit
    assert not runner.is_alive()


def test_startup_failure_sets_stop_event_and_closes_store():
    store = PodSnapshotStore()
    stop_event = Event()
    runner = HttpServerRunner(
        FailingServer(), store, stop_event, startup_timeout=0.2
    )

    with pytest.raises(HttpServerStartupError) as error:
        runner.start()

    assert isinstance(error.value.__cause__, OSError)
    assert stop_event.is_set()
    assert store.wait_for_change(0) is None


def test_unexpected_exit_stops_sampling_side():
    store = PodSnapshotStore()
    stop_event = Event()
    runner = HttpServerRunner(
        UnexpectedExitServer(), store, stop_event, startup_timeout=0.2
    )

    runner.start()

    assert stop_event.wait(0.2)
    assert store.wait_for_change(0) is None
    assert not runner.is_alive()
