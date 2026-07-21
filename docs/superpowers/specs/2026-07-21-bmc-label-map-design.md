# BMC 干扰标签映射设计

## 目标

为后续解析 BMC 返回的干扰分类结果预先定义稳定的标签编号映射。本阶段只增加定义，不修改现有 IPMI 响应格式、响应解析流程和调优动作处理流程。

## 设计

在 `src/agent/util.py` 的全局常量区域新增模块级常量 `LABEL_MAP`：

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

使用大写变量名是为了表明该映射是协议级常量。标签名称和编号严格保持既定定义，不增加反向映射、枚举类或解析函数。

## 范围

- 修改 `src/agent/util.py`。
- 增加一个单元测试，固定标签名称、编号和顺序。
- 不修改 `IpmiMessenger.get_advice()`。
- 不实现 BMC 干扰原因解析。
- 不把该映射接入 Controller HTTP 返回结果。

## 验收标准

- `util.LABEL_MAP` 与既定七个标签编号完全一致。
- 现有 BMC advice 解析行为保持不变。
- 相关测试通过。
