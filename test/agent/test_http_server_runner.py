from threading import Event, Thread, current_thread
from time import monotonic

import pytest

from agent_http.store import PodSnapshotStore
from http_server_runner import HttpServerRunner, HttpServerStartupError


class FakeServer:
    def __init__(self):
        self.started = False
        self.should_exit = False
        self.run_thread = None

    def run(self):
        self.run_thread = current_thread()
        self.started = True
        while not self.should_exit:
            Event().wait(0.001)


class FailingServer(FakeServer):
    def run(self):
        raise OSError("address already in use")


class UnexpectedExitServer(FakeServer):
    def run(self):
        self.run_thread = current_thread()
        self.started = True


class HungStartupServer(FakeServer):
    def __init__(self):
        super().__init__()
        self.release = Event()

    def run(self):
        self.run_thread = current_thread()
        self.release.wait()


class RuntimeFailingServer(FakeServer):
    def __init__(self):
        super().__init__()
        self.fail = Event()

    def run(self):
        self.run_thread = current_thread()
        self.started = True
        self.fail.wait()
        raise RuntimeError("server crashed")


def test_start_waits_until_server_is_ready_and_stop_joins_thread():
    server = FakeServer()
    caller_thread = current_thread()
    runner = HttpServerRunner(
        server=server,
        store=PodSnapshotStore(),
        stop_event=Event(),
        startup_timeout=0.2,
    )

    runner.start()
    assert server.started
    assert runner.is_alive()
    assert server.run_thread is not caller_thread
    assert server.run_thread.name == "waas-http-server"

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


def test_startup_timeout_returns_even_when_server_ignores_shutdown():
    server = HungStartupServer()
    runner = HttpServerRunner(
        server,
        PodSnapshotStore(),
        Event(),
        startup_timeout=0.01,
        shutdown_timeout=0.01,
    )
    finished = Event()
    errors = []

    def start_runner():
        try:
            runner.start()
        except BaseException as error:
            errors.append(error)
        finally:
            finished.set()

    start_time = monotonic()
    caller = Thread(target=start_runner)
    caller.start()
    try:
        assert finished.wait(0.2)
        assert monotonic() - start_time < 0.2
        assert isinstance(errors[0], HttpServerStartupError)
        assert runner.is_alive()
    finally:
        server.release.set()
        caller.join(timeout=1)
        runner.stop()

    assert not runner.is_alive()


def test_runtime_failure_is_available_to_the_main_thread():
    server = RuntimeFailingServer()
    runner = HttpServerRunner(
        server, PodSnapshotStore(), Event(), startup_timeout=0.2
    )
    runner.start()
    server.fail.set()
    assert runner.stop_event.wait(0.2)

    with pytest.raises(RuntimeError, match="HTTP server stopped unexpectedly") as error:
        runner.raise_if_failed()

    assert isinstance(error.value.__cause__, RuntimeError)
    assert str(error.value.__cause__) == "server crashed"
