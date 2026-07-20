import time
from threading import Event, Lock, Thread


class HttpServerStartupError(RuntimeError):
    """Raised when the auxiliary HTTP server cannot become ready."""


class HttpServerRunner:
    """Own the Uvicorn server thread and propagate its lifecycle to the Agent."""

    def __init__(
        self,
        server,
        store,
        stop_event: Event,
        startup_timeout: float = 5.0,
        poll_interval: float = 0.01,
    ):
        self.server = server
        self.store = store
        self.stop_event = stop_event
        self.startup_timeout = startup_timeout
        self.poll_interval = poll_interval
        self._finished = Event()
        self._state_lock = Lock()
        self._shutdown_requested = False
        self._failure = None
        self._thread = Thread(
            target=self._run,
            name="waas-http-server",
        )

    def _run(self) -> None:
        try:
            self.server.run()
        except BaseException as error:
            self._failure = error
        finally:
            self._finished.set()
            with self._state_lock:
                shutdown_requested = self._shutdown_requested
            if not shutdown_requested:
                self.stop_event.set()
                self.store.close()

    def start(self) -> None:
        self._thread.start()
        deadline = time.monotonic() + self.startup_timeout
        while not self.server.started:
            if self._finished.is_set():
                raise HttpServerStartupError(
                    "HTTP server failed to start"
                ) from self._failure
            if time.monotonic() >= deadline:
                self.stop()
                raise HttpServerStartupError("HTTP server startup timed out")
            time.sleep(self.poll_interval)

    def stop(self) -> None:
        with self._state_lock:
            self._shutdown_requested = True
        self.server.should_exit = True
        if self._thread.ident is not None:
            self._thread.join()

    def is_alive(self) -> bool:
        return self._thread.is_alive()
