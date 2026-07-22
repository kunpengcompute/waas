# 干扰原因模拟与 HTTP 返回实施计划

> **供执行 Agent 使用：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，逐项执行本计划。所有步骤使用复选框跟踪。

**目标：** 每轮成功采集和 BMC 交互后生成一个模拟干扰原因，并通过现有 HTTP 接口返回 Controller 支持的原因。

**架构：** `IpmiMessenger` 新增独立的原因获取方法，当前随机返回内部编号。主采集循环把编号写入线程安全的 `InterferenceResultStore`；HTTP 辅助线程读取最近结果，并在 API 模型边界映射为 `unknown/l3/mb/cpu`。

**技术栈：** Python 3、threading、FastAPI、Pydantic、pytest。

---

## 文件结构

- 新增 `src/agent/agent_http/interference_store.py`：保存主线程最近一次有效分析结果。
- 新增 `test/agent/test_interference_store.py`：验证 Store 的替换、节点隔离和参数校验。
- 修改 `src/agent/agent_http/models.py`：定义内部编号到 Controller 原因的边界映射。
- 修改 `test/agent/test_http_models.py`：逐一固定七个编号的映射结果。
- 修改 `src/agent/messengers/ipmi_messenger.py`：增加模拟原因获取方法。
- 新增 `test/agent/test_ipmi_interference_reason.py`：验证随机范围参数和返回值。
- 修改 `src/agent/agent_http/server.py`：从结果 Store 返回最近原因。
- 修改 `test/agent/test_http_server.py`：验证首轮前、节点不匹配和重复 GET。
- 修改 `src/agent/sampling_worker.py`：在成功 BMC 交互后写入原因。
- 修改 `test/agent/test_sampling_worker.py`：验证成功与失败场景的结果更新。
- 修改 `src/agent/main.py`：创建并注入同一个结果 Store。
- 修改 `README.en.md`：用中文说明当前模拟行为。

### 任务 1：实现原因映射和线程安全结果 Store

**文件：**

- 修改：`src/agent/agent_http/models.py`
- 新增：`src/agent/agent_http/interference_store.py`
- 修改：`test/agent/test_http_models.py`
- 新增：`test/agent/test_interference_store.py`

- [ ] **步骤 1：编写原因映射失败测试**

在 `test/agent/test_http_models.py` 中增加：

```python
import pytest

from agent_http.models import InterferenceReason, controller_reason_from_code


@pytest.mark.parametrize(
    ("reason_code", "expected"),
    [
        (0, InterferenceReason.UNKNOWN),
        (1, InterferenceReason.CPU),
        (2, InterferenceReason.CPU),
        (3, InterferenceReason.L3),
        (4, InterferenceReason.MB),
        (5, InterferenceReason.CPU),
        (6, InterferenceReason.CPU),
        (-1, InterferenceReason.UNKNOWN),
        (7, InterferenceReason.UNKNOWN),
    ],
)
def test_controller_reason_from_internal_code(reason_code, expected):
    assert controller_reason_from_code(reason_code) == expected
```

- [ ] **步骤 2：运行映射测试并确认失败**

运行：

```bash
python3 -m pytest -q test/agent/test_http_models.py
```

预期：测试收集因缺少 `controller_reason_from_code` 而失败。

- [ ] **步骤 3：实现边界映射**

在 `src/agent/agent_http/models.py` 的 `InterferenceReason` 后增加：

```python
_CONTROLLER_REASON_BY_CODE = {
    0: InterferenceReason.UNKNOWN,
    1: InterferenceReason.CPU,
    2: InterferenceReason.CPU,
    3: InterferenceReason.L3,
    4: InterferenceReason.MB,
    5: InterferenceReason.CPU,
    6: InterferenceReason.CPU,
}


def controller_reason_from_code(reason_code: int) -> InterferenceReason:
    return _CONTROLLER_REASON_BY_CODE.get(
        reason_code,
        InterferenceReason.UNKNOWN,
    )
```

- [ ] **步骤 4：运行映射测试并确认通过**

运行：

```bash
python3 -m pytest -q test/agent/test_http_models.py
```

预期：全部通过。

- [ ] **步骤 5：编写结果 Store 失败测试**

创建 `test/agent/test_interference_store.py`：

```python
from datetime import datetime, timezone

import pytest

from agent_http.interference_store import InterferenceResultStore


NOW = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)


def test_store_is_empty_before_first_result():
    assert InterferenceResultStore().current("node-a") is None


def test_store_replaces_complete_result_for_matching_node():
    store = InterferenceResultStore()

    result = store.replace("node-a", 3, NOW)

    assert store.current("node-a") == result
    assert result.node_name == "node-a"
    assert result.reason_code == 3
    assert result.timestamp == NOW
    assert store.current("node-b") is None


@pytest.mark.parametrize(
    ("node_name", "reason_code"),
    [("", 1), ("node-a", -1), ("node-a", 7)],
)
def test_store_rejects_invalid_result(node_name, reason_code):
    store = InterferenceResultStore()

    with pytest.raises(ValueError):
        store.replace(node_name, reason_code, NOW)

    assert store.current("node-a") is None
```

- [ ] **步骤 6：运行 Store 测试并确认失败**

运行：

```bash
python3 -m pytest -q test/agent/test_interference_store.py
```

预期：测试收集因缺少 `agent_http.interference_store` 而失败。

- [ ] **步骤 7：实现 Store**

创建 `src/agent/agent_http/interference_store.py`：

```python
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
        self,
        node_name: str,
        reason_code: int,
        timestamp: datetime,
    ) -> InterferenceResult:
        normalized_node_name = node_name.strip()
        if not normalized_node_name:
            raise ValueError("node name must not be empty")
        if reason_code < 0 or reason_code > 6:
            raise ValueError(f"invalid interference reason code: {reason_code}")

        result = InterferenceResult(
            node_name=normalized_node_name,
            reason_code=reason_code,
            timestamp=timestamp,
        )
        with self._lock:
            self._result = result
        return result

    def current(self, node_name: str) -> InterferenceResult | None:
        with self._lock:
            result = self._result
        if result is None or result.node_name != node_name.strip():
            return None
        return result
```

- [ ] **步骤 8：运行任务 1 测试并提交**

运行：

```bash
python3 -m pytest -q \
  test/agent/test_http_models.py \
  test/agent/test_interference_store.py
```

预期：全部通过。

提交：

```bash
git add \
  src/agent/agent_http/models.py \
  src/agent/agent_http/interference_store.py \
  test/agent/test_http_models.py \
  test/agent/test_interference_store.py
git commit -m "feat(agent): store mapped interference results"
```

### 任务 2：新增 Messenger 模拟原因接口

**文件：**

- 修改：`src/agent/messengers/ipmi_messenger.py`
- 新增：`test/agent/test_ipmi_interference_reason.py`

- [ ] **步骤 1：编写失败测试**

创建 `test/agent/test_ipmi_interference_reason.py`：

```python
from messengers.ipmi_messenger import IpmiMessenger


def test_get_interference_reason_uses_full_label_range(monkeypatch):
    captured = []

    def fake_randint(start, end):
        captured.append((start, end))
        return 4

    monkeypatch.setattr(
        "messengers.ipmi_messenger.random.randint",
        fake_randint,
    )

    assert IpmiMessenger().get_interference_reason() == 4
    assert captured == [(0, 6)]
```

- [ ] **步骤 2：运行测试并确认方法不存在**

运行：

```bash
python3 -m pytest -q test/agent/test_ipmi_interference_reason.py
```

预期：以 `AttributeError` 失败。

- [ ] **步骤 3：实现随机原因接口**

在 `src/agent/messengers/ipmi_messenger.py` 中增加导入：

```python
import random
```

在 `IpmiMessenger` 中增加：

```python
def get_interference_reason(self) -> int:
    return random.randint(
        min(util.LABEL_MAP.values()),
        max(util.LABEL_MAP.values()),
    )
```

- [ ] **步骤 4：运行测试并提交**

运行：

```bash
python3 -m pytest -q test/agent/test_ipmi_interference_reason.py
```

预期：`1 passed`。

提交：

```bash
git add \
  src/agent/messengers/ipmi_messenger.py \
  test/agent/test_ipmi_interference_reason.py
git commit -m "feat(agent): simulate BMC interference reason"
```

### 任务 3：让 HTTP 返回最近一次映射结果

**文件：**

- 修改：`src/agent/agent_http/server.py`
- 修改：`test/agent/test_http_server.py`

- [ ] **步骤 1：编写 HTTP 失败测试**

在 `test/agent/test_http_server.py` 中增加辅助构造和测试：

```python
from datetime import datetime, timezone

from agent_http.interference_store import InterferenceResultStore


def app_with_results(result_store):
    return create_app(PodSnapshotStore(), result_store)


def test_interference_returns_unknown_before_first_result():
    response = request(
        app_with_results(InterferenceResultStore()),
        "GET",
        "/v1/interference?node_name=node-a",
    )

    assert response.status_code == 200
    assert response.json()["reason"] == "unknown"


def test_interference_returns_stored_mapped_reason_repeatedly():
    results = InterferenceResultStore()
    results.replace(
        "node-a",
        4,
        datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
    )
    application = app_with_results(results)

    first = request(
        application,
        "GET",
        "/v1/interference?node_name=node-a",
    )
    second = request(
        application,
        "GET",
        "/v1/interference?node_name=node-a",
    )

    assert first.json()["reason"] == "mb"
    assert second.json() == first.json()


def test_interference_returns_unknown_for_another_node():
    results = InterferenceResultStore()
    results.replace(
        "node-a",
        3,
        datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
    )

    response = request(
        app_with_results(results),
        "GET",
        "/v1/interference?node_name=node-b",
    )

    assert response.json()["reason"] == "unknown"
```

- [ ] **步骤 2：运行 HTTP 测试并确认 `create_app` 尚不接收结果 Store**

运行：

```bash
python3 -m pytest -q test/agent/test_http_server.py
```

预期：新增测试以 `TypeError` 失败。

- [ ] **步骤 3：实现 HTTP 读取和映射**

在 `server.py` 中导入：

```python
from agent_http.interference_store import InterferenceResultStore
from agent_http.models import controller_reason_from_code
```

修改应用工厂签名：

```python
def create_app(
    store: PodSnapshotStore,
    interference_store: InterferenceResultStore | None = None,
) -> FastAPI:
```

修改 GET 路由末尾：

```python
if interference_store is None:
    return InterferenceResponse.unknown(normalized_node_name)

result = interference_store.current(normalized_node_name)
if result is None:
    return InterferenceResponse.unknown(normalized_node_name)

return InterferenceResponse(
    node_name=normalized_node_name,
    reason=controller_reason_from_code(result.reason_code),
    ttl_seconds=0,
    items=(),
)
```

- [ ] **步骤 4：运行 HTTP 测试并提交**

运行：

```bash
python3 -m pytest -q \
  test/agent/test_http_models.py \
  test/agent/test_interference_store.py \
  test/agent/test_http_server.py
```

预期：全部通过。

提交：

```bash
git add src/agent/agent_http/server.py test/agent/test_http_server.py
git commit -m "feat(agent): return latest interference reason over HTTP"
```

### 任务 4：采集成功后保存模拟原因

**文件：**

- 修改：`src/agent/sampling_worker.py`
- 修改：`test/agent/test_sampling_worker.py`

- [ ] **步骤 1：编写成功写入的失败测试**

在 `test/agent/test_sampling_worker.py` 中增加：

```python
from agent_http.interference_store import InterferenceResultStore


def test_successful_bmc_cycle_stores_interference_reason():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))
    results = InterferenceResultStore()

    class ReasonMessenger(FakeMessenger):
        def get_interference_reason(self):
            return 3

    worker = SamplingWorker(
        store=store,
        stop_event=stop,
        counter_factory=lambda paths: FakeCounter(paths, created, sampled),
        interval=0,
        processor=FakeProcessor(),
        messenger=ReasonMessenger(),
        handler=FakeHandler(),
        interference_store=results,
        retry_interval=0.01,
    )
    thread = Thread(target=worker.run)
    thread.start()
    wait_until(lambda: results.current("node-a") is not None)
    stop.set()
    store.close()
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert results.current("node-a").reason_code == 3


def test_failed_bmc_cycle_does_not_replace_interference_reason():
    store, stop, created, sampled = PodSnapshotStore(), Event(), [], []
    store.replace(request(pods=(pod(),)))
    results = InterferenceResultStore()

    class FailingMessenger(FakeMessenger):
        def send_data(self, payload):
            stop.set()
            raise RuntimeError("BMC failed")

        def get_interference_reason(self):
            raise AssertionError("failed BMC cycle must not produce a reason")

    worker = SamplingWorker(
        store=store,
        stop_event=stop,
        counter_factory=lambda paths: FakeCounter(paths, created, sampled),
        interval=0,
        processor=FakeProcessor(),
        messenger=FailingMessenger(),
        handler=FakeHandler(),
        interference_store=results,
        retry_interval=0.01,
    )

    worker.run()

    assert results.current("node-a") is None
```

- [ ] **步骤 2：运行测试并确认构造参数尚不存在**

运行：

```bash
python3 -m pytest -q \
  test/agent/test_sampling_worker.py::test_successful_bmc_cycle_stores_interference_reason \
  test/agent/test_sampling_worker.py::test_failed_bmc_cycle_does_not_replace_interference_reason
```

预期：以 `TypeError` 失败。

- [ ] **步骤 3：实现成功周期写入**

在 `sampling_worker.py` 导入：

```python
from datetime import datetime, timezone
```

在构造函数末尾增加：

```python
interference_store=None,
```

保存依赖：

```python
self.interference_store = interference_store
```

在 `get_advice()` 和可选 `handler.apply()` 成功后增加：

```python
if self.interference_store is not None:
    reason_code = self.messenger.get_interference_reason()
    self.interference_store.replace(
        snapshot.node_name,
        reason_code,
        datetime.now(timezone.utc),
    )
```

该代码保留在现有 downstream `try` 内，因此 BMC 调用或原因获取失败时只记录错误，不覆盖上一次结果。

- [ ] **步骤 4：运行 SamplingWorker 全部测试**

运行：

```bash
python3 -m pytest -q test/agent/test_sampling_worker.py
```

预期：全部通过。

- [ ] **步骤 5：提交采集接入**

```bash
git add src/agent/sampling_worker.py test/agent/test_sampling_worker.py
git commit -m "feat(agent): store reason after successful BMC cycle"
```

### 任务 5：在主入口注入结果 Store 并完成验证

**文件：**

- 修改：`src/agent/main.py`
- 修改：`test/agent/test_main.py`
- 修改：`README.en.md`

- [ ] **步骤 1：编写主入口依赖接线失败测试**

在 `main.py` 中新增一个便于验证且只负责注入的函数，并先在 `test/agent/test_main.py` 中定义期望：

```python
def test_create_worker_passes_interference_store(monkeypatch):
    main = load_main(monkeypatch)
    captured = {}
    result_store = object()

    class FakeSamplingWorker:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(main, "SamplingWorker", FakeSamplingWorker)

    worker = main._create_worker(
        store=object(),
        stop_event=object(),
        interval=1,
        processor=object(),
        messenger=object(),
        handler=object(),
        recorder=None,
        interference_store=result_store,
    )

    assert isinstance(worker, FakeSamplingWorker)
    assert captured["interference_store"] is result_store
```

- [ ] **步骤 2：运行测试并确认 `_create_worker` 尚不存在**

运行：

```bash
python3 -m pytest -q test/agent/test_main.py::test_create_worker_passes_interference_store
```

预期：以 `AttributeError` 失败。

- [ ] **步骤 3：实现主入口接线**

在 `main.py` 导入：

```python
from agent_http.interference_store import InterferenceResultStore
```

增加：

```python
def _create_worker(
    store,
    stop_event,
    interval,
    processor,
    messenger,
    handler,
    recorder,
    interference_store,
):
    return SamplingWorker(
        store=store,
        stop_event=stop_event,
        counter_factory=_create_counter,
        interval=interval,
        processor=processor,
        messenger=messenger,
        handler=handler,
        recorder=recorder,
        interference_store=interference_store,
    )
```

在 `main()` 中创建一次：

```python
interference_store = InterferenceResultStore()
```

使用 `_create_worker(...)` 创建 Worker，并把同一对象传给：

```python
create_app(store, interference_store)
```

- [ ] **步骤 4：运行主入口和 HTTP 测试**

运行：

```bash
python3 -m pytest -q \
  test/agent/test_main.py \
  test/agent/test_http_server.py \
  test/agent/test_sampling_worker.py
```

预期：全部通过。

- [ ] **步骤 5：更新中文运行说明**

在 `README.en.md` 的 Controller HTTP 对接部分增加：

```markdown
当前真实 BMC 干扰分类解析尚未接入。Agent 在每轮成功采集和 BMC 交互后随机生成一个 `0～6` 的内部原因编号，并保存为最近结果；`GET /v1/interference` 将其映射为 Controller 支持的 `unknown/l3/mb/cpu`。同一采集周期内重复查询不会重新生成原因。
```

- [ ] **步骤 6：执行最终验证**

运行：

```bash
git diff --check
python3 -m compileall -q src/agent
python3 -m pytest -q \
  test/agent/test_bmc_label_map.py \
  test/agent/test_http_models.py \
  test/agent/test_interference_store.py \
  test/agent/test_ipmi_interference_reason.py \
  test/agent/test_pod_store.py \
  test/agent/test_http_server.py \
  test/agent/test_http_server_runner.py \
  test/agent/test_sample_cgroups.py \
  test/agent/test_sampling_worker.py \
  test/agent/test_main.py
```

预期：格式和编译检查以状态码 0 结束，所有聚焦测试通过。

在 `/home/yanxiang/Desktop/cloud-native` 运行：

```bash
go test ./pkg/kunpeng-qos-controller/dynamiccontrol/...
```

预期：状态码 0，现有 Controller 协议兼容。

- [ ] **步骤 7：提交接线和文档**

```bash
git add src/agent/main.py test/agent/test_main.py README.en.md
git commit -m "feat(agent): expose simulated interference results"
```

## 完成标准

- `get_advice()` 的返回类型和调用流程保持不变。
- 每轮成功采集和 BMC 交互后调用一次 `get_interference_reason()`。
- 首轮成功结果前返回 `unknown`。
- 同一采集周期内重复 GET 返回相同结果。
- 七个内部编号按确认映射转换为 Controller 原因。
- 失败或陈旧采样不覆盖最近有效结果。
- 全部聚焦测试和 Controller 动态控制包测试通过。
