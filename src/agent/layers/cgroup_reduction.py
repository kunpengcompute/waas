import os
import json
import logging
from data_process import Layer
from typing import Dict, List, Union, Set
from calculators import _cpy, _div, _add, IPC_VAL_MAX


class CgroupReduction(Layer):
    def __init__(self):
        pass

    def process(self, data):
        if len(data) < 1:
            return data

        valid_core_list = []
        first_core_metric = None

        # 遍历所有 cgroup、所有核心
        for cgroup_path, core_items in data.items():
            for core_id, metrics in core_items.items():
                # 记录第一条数据，用于兜底
                if first_core_metric is None:
                    first_core_metric = metrics.copy()

                inst_value = metrics.get("INST_RETIRED", 0.0)

                # 只保留 INST_RETIRED 不为 0 的核心
                if inst_value != 0:
                    valid_core_list.append(metrics)

        if not valid_core_list:
            logging.warning("不存在 INST_RETIRED 不为 0 的有效核心")
            cgroup_data = {
                "0": first_core_metric
            }
            return cgroup_data

        # 初始化汇总结构
        avg_result = {}
        metric_names = valid_core_list[0].keys()

        for metric in metric_names:
            avg_result[metric] = 0.0

        # 累加所有有效核心指标
        for core_metric in valid_core_list:
            for metric_name, val in core_metric.items():
                avg_result[metric_name] += val

        # 求取平均值
        valid_count = len(valid_core_list)

        for metric_name in avg_result:
            avg_result[metric_name] /= valid_count

        # 统一外层结构为 {"0": 均值字典}
        cgroup_data = {
            "0": avg_result
        }

        return cgroup_data