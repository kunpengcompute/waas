# 干扰原因模拟与 HTTP 返回设计

## 目标

在真实 BMC 干扰原因解析尚未完成前，用 `0～6` 的随机分类结果模拟分析输出，并通过现有 `GET /v1/interference` 接口返回给 Controller。模拟结果的产生时机应与未来真实行为一致：每完成一轮指标采集和 BMC 交互后更新一次，而不是每次 HTTP 查询时临时生成。

## 设计原则

- 保留 `get_advice()` 的现有职责和返回类型，不影响 CORE/SOC 调优动作链路。
- 新增独立的 `get_interference_reason()`，当前返回一个 `0～6` 的整数。
- 采集循环负责在一轮 BMC 交互完成后获取原因并保存。
- HTTP 层只读取最近一次结果并完成 Controller 协议映射，不触发随机生成或 BMC 调用。
- 后续真实解析只替换 `get_interference_reason()` 的实现，Store 和 HTTP 接口保持稳定。

## 标签与 Controller 原因映射

内部标签定义沿用 `util.LABEL_MAP`：

```python
LABEL_MAP = {
    "base": 0,
    "compute": 1,
    "l2": 2,
    "l3": 3,
    "membw": 4,
    "tlb": 5,
    "frontend": 6,
}
```

Controller 当前只支持 `unknown/l3/mb/cpu`，临时映射为：

| 内部编号 | 内部标签 | Controller 原因 |
|---:|---|---|
| 0 | `base` | `unknown` |
| 1 | `compute` | `cpu` |
| 2 | `l2` | `cpu` |
| 3 | `l3` | `l3` |
| 4 | `membw` | `mb` |
| 5 | `tlb` | `cpu` |
| 6 | `frontend` | `cpu` |

`base` 明确表示无干扰，因此映射为 `unknown`，Controller 不执行调优动作。

## 组件设计

### `IpmiMessenger.get_interference_reason()`

新增方法：

```python
def get_interference_reason(self) -> int:
    return random.randint(0, 6)
```

当前随机范围必须包含首尾值。测试通过替换随机函数返回固定值，避免非确定性。未来该方法改为解析 BMC 返回内容。

### `InterferenceResultStore`

新增线程安全结果 Store，保存：

- `node_name`
- 内部原因编号 `reason_code`
- 结果产生时间

主采集线程写入，HTTP 辅助线程读取。未产生结果或查询节点不匹配时返回空结果，由 HTTP 层转换为 `unknown`。

结果对象不可变；Store 使用锁保护整体替换和读取，HTTP 不会看到部分更新状态。

### `SamplingWorker`

一轮正常流程调整为：

```text
采集指标
→ DataProcessor
→ send_data
→ get_advice
→ 本地应用 advice
→ get_interference_reason
→ 写入 InterferenceResultStore
```

只有本轮采集、数据处理和 BMC 交互成功完成后才更新原因。采集失败、BMC 调用异常或目标在采集期间变化时，不覆盖上一次有效结果。

原因结果使用本轮采集目标对应的 `node_name`。空采集目标不会生成新原因。

### HTTP 接口

`create_app()` 同时接收 Pod Store 和干扰结果 Store。`GET /v1/interference?node_name=...`：

1. 读取该节点最近一次内部原因编号。
2. 按既定映射转换为 `InterferenceReason`。
3. 返回 `items=[]`、`ttl_seconds=0`。
4. 没有结果或节点不匹配时返回现有 `unknown` 响应。

HTTP GET 不改变已保存结果，因此同一采集周期内重复查询返回相同原因。

## 并发与生命周期

- `SamplingWorker` 在主线程中写入结果 Store。
- FastAPI/Uvicorn 辅助线程只读取结果 Store。
- Store 不持有 `PerfCount`、Messenger 或 HTTP 对象。
- Agent 重启后结果清空，第一轮采集完成前返回 `unknown`。
- Agent 关闭时不需要单独持久化结果。

## 测试策略

- `get_interference_reason()` 的返回值位于闭区间 `[0, 6]`，并可通过替换随机函数确定结果。
- 结果 Store 覆盖未初始化、整体替换、节点匹配和节点不匹配。
- 七个内部编号逐一验证 Controller 映射。
- HTTP 在首轮结果前返回 `unknown`。
- HTTP 在保存结果后返回映射原因，多次 GET 保持一致。
- SamplingWorker 只在一轮成功交互后更新结果，失败或陈旧样本不更新。
- 现有 CORE/SOC advice 处理测试继续通过。

## 不在本次范围内

- 解析真实 BMC 干扰原因字节格式。
- 修改 Controller 支持的原因枚举。
- 返回 Pod 级 `items` 或干扰分数。
- 设计结果有效期；`ttl_seconds` 暂时保持 `0`。
- 持久化历史原因或进程重启前的结果。

## 验收标准

- 每轮成功采集和 BMC 交互最多产生一个模拟原因。
- Controller 能通过现有接口取得映射后的 `unknown/l3/mb/cpu`。
- 同一采集周期内重复 GET 不会重新随机。
- `get_advice()` 和现有本地调优动作行为不变。
- 首轮结果前、节点不匹配或无有效结果时安全返回 `unknown`。
