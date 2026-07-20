# HTTP 辅助线程生命周期实施计划

> **供执行 Agent 使用：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，逐项执行本计划。所有步骤使用复选框跟踪。

**目标：** 让原有采样与 IPMI/BMC 循环运行在 Agent 主线程，只把 FastAPI/Uvicorn HTTP 服务放入辅助线程，并在 HTTP 启动失败或意外退出时终止整个 Agent。

**架构：** 新增 `HttpServerRunner`，集中管理 Uvicorn 线程的启动确认、异常传播、意外退出通知和正常停止。`main.py` 仍负责组装依赖，但直接在主线程调用 `SamplingWorker.run()`；HTTP 线程与主采集循环继续通过 `PodSnapshotStore` 和 `stop_event` 通信。

**技术栈：** Python 3、`threading.Thread`、`threading.Event`、FastAPI、Uvicorn、pytest。

---

## 文件结构

- 新增 `src/agent/http_server_runner.py`：管理 Uvicorn 辅助线程的完整生命周期。
- 新增 `test/agent/test_http_server_runner.py`：验证启动成功、启动失败、意外退出和正常停止。
- 修改 `src/agent/main.py`：主线程运行采样循环，后台线程运行 HTTP。
- 修改 `test/agent/test_main.py`：验证启动顺序、主线程归属及清理行为。
- 修改 `README.md`：把运行架构说明改为“主线程采集、辅助线程 HTTP”。

### 任务 1：实现 HTTP 辅助线程管理器

**文件：**

- 新增：`src/agent/http_server_runner.py`
- 新增：`test/agent/test_http_server_runner.py`

- [ ] **步骤 1：编写 HTTP 管理器生命周期的失败测试**

创建测试中的可控假 Server：

```python
from threading import Event

import pytest

from agent_http.store import PodSnapshotStore
from http_server_runner import HttpServerRunner, HttpServerStartupError


class FakeServer:
    def __init__(self):
        self.started = False
        self.should_exit = False
        self.entered = Event()

    def run(self):
        self.started = True
        self.entered.set()
        while not self.should_exit:
            Event().wait(0.001)


class FailingServer(FakeServer):
    def run(self):
        raise OSError("address already in use")


class UnexpectedExitServer(FakeServer):
    def run(self):
        self.started = True
        self.entered.set()


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
```

- [ ] **步骤 2：运行测试并确认因为管理器尚不存在而失败**

运行：

```bash
python3 -m pytest -q test/agent/test_http_server_runner.py
```

预期：测试收集失败，提示 `No module named 'http_server_runner'`。

- [ ] **步骤 3：实现 HTTP 管理器完整生命周期**

在 `src/agent/http_server_runner.py` 中实现：

```python
import time
from threading import Event, Lock, Thread


class HttpServerStartupError(RuntimeError):
    pass


class HttpServerRunner:
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
                raise HttpServerStartupError("HTTP server failed to start") from self._failure
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
```

- [ ] **步骤 4：运行全部管理器测试并确认通过**

运行：

```bash
python3 -m pytest -q test/agent/test_http_server_runner.py
```

预期：全部通过且没有线程异常警告。

- [ ] **步骤 5：提交 HTTP 管理器**

提交：

```bash
git add src/agent/http_server_runner.py test/agent/test_http_server_runner.py
git commit -m "feat(agent): run HTTP server in auxiliary thread"
```

### 任务 2：让主线程运行原有采集循环

**文件：**

- 修改：`src/agent/main.py:70-118`
- 修改：`test/agent/test_main.py`

- [ ] **步骤 1：为生命周期编排编写失败测试**

在 `test/agent/test_main.py` 中添加：

```python
from threading import Event, current_thread


def test_run_agent_runs_sampling_on_caller_thread_and_cleans_up(monkeypatch):
    main = load_main(monkeypatch)
    calls = []

    class FakeWorker:
        def run(self):
            calls.append(("worker", current_thread()))

    class FakeHttpRunner:
        def start(self):
            calls.append(("http-start", current_thread()))

        def stop(self):
            calls.append(("http-stop", current_thread()))

    class FakeStore:
        def close(self):
            calls.append(("store-close", current_thread()))

    stop_event = Event()
    caller_thread = current_thread()

    main._run_agent(FakeWorker(), FakeHttpRunner(), FakeStore(), stop_event)

    assert calls == [
        ("http-start", caller_thread),
        ("worker", caller_thread),
        ("store-close", caller_thread),
        ("http-stop", caller_thread),
    ]
    assert stop_event.is_set()


def test_run_agent_does_not_start_sampling_when_http_start_fails(monkeypatch):
    main = load_main(monkeypatch)
    worker_called = False

    class FakeWorker:
        def run(self):
            nonlocal worker_called
            worker_called = True

    class FakeHttpRunner:
        def start(self):
            raise RuntimeError("HTTP failed")

        def stop(self):
            pass

    class FakeStore:
        def close(self):
            pass

    with pytest.raises(RuntimeError, match="HTTP failed"):
        main._run_agent(FakeWorker(), FakeHttpRunner(), FakeStore(), Event())

    assert not worker_called
```

同时在文件顶部添加 `import pytest`。

- [ ] **步骤 2：运行测试并确认 `_run_agent` 尚不存在**

运行：

```bash
python3 -m pytest -q test/agent/test_main.py
```

预期：新增测试以 `AttributeError: module 'main' has no attribute '_run_agent'` 失败。

- [ ] **步骤 3：实现主线程生命周期编排**

在 `main.py` 中导入：

```python
from http_server_runner import HttpServerRunner
```

增加：

```python
def _run_agent(worker, http_runner, store, stop_event):
    try:
        http_runner.start()
        worker.run()
    finally:
        stop_event.set()
        store.close()
        http_runner.stop()
```

将 `main()` 中原有的 `worker_thread` 创建和启动删除，改为：

```python
config = uvicorn.Config(
    create_app(store),
    host=args.http_host,
    port=args.http_port,
    log_level="info",
)
http_runner = HttpServerRunner(
    server=uvicorn.Server(config),
    store=store,
    stop_event=stop_event,
)
_run_agent(worker, http_runner, store, stop_event)
```

- [ ] **步骤 4：运行主入口测试并确认通过**

运行：

```bash
python3 -m pytest -q test/agent/test_main.py
```

预期：全部通过；采样循环由调用 `main()` 的线程直接执行。

- [ ] **步骤 5：运行采样和 HTTP 相关回归测试**

运行：

```bash
python3 -m pytest -q \
  test/agent/test_http_server_runner.py \
  test/agent/test_http_server.py \
  test/agent/test_pod_store.py \
  test/agent/test_sampling_worker.py \
  test/agent/test_main.py
```

预期：全部通过，没有未处理线程异常。

- [ ] **步骤 6：提交主线程编排修改**

```bash
git add src/agent/main.py test/agent/test_main.py
git commit -m "refactor(agent): keep sampling loop on main thread"
```

### 任务 3：更新中文运行说明并完成验证

**文件：**

- 修改：`README.md`

- [ ] **步骤 1：更新线程模型说明**

在 HTTP 集成说明中明确写入：

```markdown
### 线程模型

- Agent 主线程运行原有的 PMU 采集、数据处理和 IPMI/BMC 循环。
- FastAPI/Uvicorn 运行在独立的 HTTP 辅助线程中。
- `PodSnapshotStore` 在线程之间传递 Controller 下发的 Pod cgroup 完整快照。
- HTTP 服务启动失败或运行中意外退出时，Agent 主采集循环会停止，整个进程退出。
```

- [ ] **步骤 2：检查代码和文档格式**

运行：

```bash
git diff --check
python3 -m compileall -q src/agent
```

预期：两个命令均以状态码 0 结束。

- [ ] **步骤 3：运行全部聚焦测试**

运行：

```bash
python3 -m pytest -q \
  test/agent/test_http_models.py \
  test/agent/test_pod_store.py \
  test/agent/test_http_server.py \
  test/agent/test_http_server_runner.py \
  test/agent/test_sample_cgroups.py \
  test/agent/test_sampling_worker.py \
  test/agent/test_main.py
```

预期：全部通过。

- [ ] **步骤 4：验证 Controller 侧协议兼容性**

在 `/home/yanxiang/Desktop/cloud-native` 中运行：

```bash
go test ./pkg/kunpeng-qos-controller/dynamiccontrol/...
```

预期：状态码 0。

- [ ] **步骤 5：提交文档**

```bash
git add README.md
git commit -m "docs(agent): describe auxiliary HTTP thread"
```

## 完成标准

- 主线程直接运行 `SamplingWorker.run()`。
- 只有 HTTP/Uvicorn 运行在新增辅助线程中。
- HTTP 启动失败时不会进入采集循环。
- HTTP 意外退出时会唤醒并终止主采集循环。
- 正常退出会停止并回收 HTTP 线程、counter 和 recorder。
- HTTP 协议、Pod 快照模型和 `kperf` cgroup 参数保持不变。
- 所有聚焦测试和 Controller 动态控制包测试通过。
