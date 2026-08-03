import os
import pandas as pd
import numpy as np
import pickle

import warnings

# 屏蔽警告：训练时数据带有列名，推理时不带列名会触发警告，不影响推理结果
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=(
        "X does not have valid feature names, "
        "but RandomForestClassifier was fitted with feature names"
    )
)

# 配置信息（和训练代码保持一致）
label_map = {
    0: "base",
    1: "compute",
    2: "l2",
    3: "l3",
    4: "membw",
    5: "tlb",
    6: "frontend",
}

selected_feas = [
    "l3.mpi",
    "cpu.ipc",
    "sve.ratio",
    "l3.mr",
    "l1d.refer/l1i.refer",
]

model_path = "rf_spec.pkl"


# 加载训练好的随机森林模型
def load_model(model_file):
    with open(model_file, "rb") as f:
        model = pickle.load(f)

    return model


def payload_to_input(payload, feas_order):
    """
    将 payload 结构转为模型可输入的特征列表嵌套结构。

    :param payload:
        {
            "start_time": ...,
            "stop_time": ...,
            "cores": ...,
            "all": {
                group_id: feature_dict
            }
        }
    :param feas_order:
        list，模型训练时的特征顺序，例如：
        [
            "l3.mpi",
            "cpu.ipc",
            "sve.ratio",
            "l3.mr",
            "l1d.refer/l1i.refer"
        ]
    :return:
        feat_list：
        [
            [特征1, 特征2, ...],
            [另一组特征, ...]
        ]

        二维列表，每行对应一个分组。
    """
    all_groups = payload["all"]
    feat_list = []

    for _, feature_dict in all_groups.items():
        row = []

        for feat_name in feas_order:
            # 缺失特征填充 0.0
            val = feature_dict.get(feat_name, 0.0)
            row.append(val)

        feat_list.append(row)

    return feat_list[0]


# 单条样本推理
def predict_single_sample(model, feature_list):
    """
    feature_list 的顺序必须严格和 selected_feas 一致：

    [
        "l3.mpi",
        "cpu.ipc",
        "sve.ratio",
        "l3.mr",
        "l1d.refer/l1i.refer"
    ]
    """
    arr = np.array(feature_list).reshape(1, -1)
    pred_id = model.predict(arr)[0]
    pred_class = label_map[pred_id]

    return pred_id, pred_class


def infer(payload):
    # 加载训练好的 Random Forest 模型
    rf_model = load_model(model_path)

    # 将 cgroup 数据转换为模型输入
    sample_features = payload_to_input(payload, selected_feas)

    # 单样本推理：
    # pred_id 为模型输出编号 0～6
    # pred_class 为对应的干扰类型
    pred_id, pred_class = predict_single_sample(
        rf_model,
        sample_features,
    )

    return pred_id


if __name__ == "__main__":
    # 加载模型
    rf_model = load_model(model_path)
    print("模型加载完成！")

    # 单条样本推理示例
    # 样本特征顺序：
    # l3.mpi, cpu.ipc, sve.ratio, l3.mr, l1d.refer/l1i.refer
    sample_features = [
        0.25,
        1.8,
        0.12,
        0.08,
        2.6,
    ]

    pred_id, pred_cls = predict_single_sample(
        rf_model,
        sample_features,
    )

    print(
        f"\n单条样本预测结果："
        f"类别编号={pred_id}，"
        f"业务标签={pred_cls}"
    )