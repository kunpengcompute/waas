import os
import json
import logging
from data_process import Layer
from typing import Dict, List, Union, Set
from calculators import _cpy, _div, _add, IPC_VAL_MAX

NUMA_ROOT = "/sys/devices/system/node/"

def parse_cpulist(cpulist_str: str) -> Set[int]:
    """解析cpulist字符串（如"0-2,4"）为逻辑核心集合"""
    cores = set()
    for part in cpulist_str.strip().split(','):
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-')
            cores.update(range(int(start), int(end) + 1))
        else:
            cores.add(int(part))
    return cores


def get_numa_node_mapping() -> Union[Dict[int, Set[int]], str]:
    """获取NUMA节点与对应逻辑核心的映射关系（核心用set存储）
    返回：字典（节点ID: 逻辑核心集合）或错误信息字符串
    """
    numa_root = "/sys/devices/system/node/"
    try:
        # 筛选所有NUMA节点目录（node0, node1...）
        nodes = [name for name in os.listdir(numa_root) if name.startswith("node")]
        if not nodes:
            return "未检测到NUMA节点（目录下无nodeX条目）"

        # 构建节点-逻辑核心映射（值为set集合）
        return {
            int(node.replace("node", "")): parse_cpulist(
                open(os.path.join(numa_root, node, "cpulist"), "r").read()
            )
            for node in nodes
        }

    except FileNotFoundError:
        return "系统不支持NUMA（无/sys/devices/system/node目录）"
    except PermissionError:
        return "权限不足，无法读取NUMA目录"
    except Exception as e:
        return f"获取失败：{str(e)}"



class NumaReduction(Layer):
    def __init__(self):
        self.numa_groups = get_numa_node_mapping()

    '''
    计算该核心id所属numa
    '''
    def get_belong_numa(self, core_id):
        for numa in self.numa_groups:
            if core_id in self.numa_groups[numa]:
                return numa
        return None

    def process(self, data):
        if len(data) < 1:
            return data
        # 初始化结果
        numa_data = {
            numa_id: {
                metric_name: 0.0
                for metric_name in data[next(iter(data))]
            }
            for numa_id in self.numa_groups.keys()
        }
        # 以numa为单位汇总指标和
        for core_id in data:
            numa_id = self.get_belong_numa(core_id)
            for metric_name, metric_value in data[core_id].items():
                numa_data[numa_id][metric_name] += metric_value
        # 单numa内指标取平均
        for numa_id in numa_data.keys():
            for metric_name in numa_data[numa_id].keys():
                numa_data[numa_id][metric_name] /= len(self.numa_groups[numa_id])

        return numa_data
