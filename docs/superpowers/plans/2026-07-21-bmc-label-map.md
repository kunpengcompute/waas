# BMC 干扰标签映射实施计划

> **供执行 Agent 使用：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，逐项执行本计划。所有步骤使用复选框跟踪。

**目标：** 在现有 BMC 响应解析工具模块中定义稳定的七类干扰标签编号映射。

**架构：** 将映射作为 `src/agent/util.py` 的模块级常量 `LABEL_MAP`，暂不增加解析函数或反向映射。通过独立单元测试固定名称、编号和声明顺序，防止后续协议解析时发生无意修改。

**技术栈：** Python 3、pytest。

---

## 文件结构

- 修改 `src/agent/util.py`：增加协议级常量 `LABEL_MAP`。
- 新增 `test/agent/test_bmc_label_map.py`：固定映射内容和顺序。

### 任务 1：定义 BMC 干扰标签映射

**文件：**

- 修改：`src/agent/util.py:9`
- 新增：`test/agent/test_bmc_label_map.py`

- [ ] **步骤 1：编写失败测试**

创建 `test/agent/test_bmc_label_map.py`：

```python
import util


def test_bmc_label_map_matches_protocol_definition():
    assert list(util.LABEL_MAP.items()) == [
        ("base", 0),
        ("compute", 1),
        ("l2", 2),
        ("l3", 3),
        ("membw", 4),
        ("tlb", 5),
        ("frontend", 6),
    ]
```

- [ ] **步骤 2：运行测试并确认失败原因正确**

运行：

```bash
python3 -m pytest -q test/agent/test_bmc_label_map.py
```

预期：测试以 `AttributeError: module 'util' has no attribute 'LABEL_MAP'` 失败。

- [ ] **步骤 3：添加最小实现**

在 `src/agent/util.py` 的全局常量区域加入：

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

- [ ] **步骤 4：运行新增测试并确认通过**

运行：

```bash
python3 -m pytest -q test/agent/test_bmc_label_map.py
```

预期：`1 passed`。

- [ ] **步骤 5：运行相关回归验证**

运行：

```bash
git diff --check
python3 -m compileall -q src/agent
python3 -m pytest -q \
  test/agent/test_bmc_label_map.py \
  test/agent/test_sampling_worker.py \
  test/agent/test_main.py
```

预期：三个命令均以状态码 0 结束，测试全部通过。

- [ ] **步骤 6：提交实现**

```bash
git add src/agent/util.py test/agent/test_bmc_label_map.py
git commit -m "feat(agent): define BMC interference labels"
```

## 完成标准

- `util.LABEL_MAP` 精确包含七个既定标签及其编号。
- 映射声明顺序与协议定义一致。
- 现有 BMC advice 解析和 HTTP 行为不变。
- 新增测试及相关回归测试通过。
