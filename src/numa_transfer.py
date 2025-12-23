# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import time
import psutil
import glob
from typing import Dict, List, Set, Tuple, Optional

import util
import waas_log as logging


class NumaTransfer:
    def __init__(self, interval: float = 1.0):
        """
        初始化 NumaTransfer
        :param cgroup_root: cgroup 挂载根目录
        :param interval: 采样计算 CPU 利用率的时间间隔(秒)
        """
        self.cpuset_root, _ = util.find_cpuset_mountpoint()
        self.cpuacct_root = self.cpuset_root.replace(util.CPUSET, util.CPUACCT)
        self.interval = interval
        
        # 1. 初始化拓扑结构 {numa_node_id: {cpu_id, ...}}
        self.numa_topology: Dict[int, Set[int]] = self._get_numa_topology()
        self.cpu_to_numa: Dict[int, int] = {}
        for node, cpus in self.numa_topology.items():
            for cpu in cpus:
                self.cpu_to_numa[cpu] = node

    def _get_numa_topology(self) -> Dict[int, Set[int]]:
        """
        读取系统 NUMA 拓扑
        """
        topology = {}
        # 尝试读取 /sys/devices/system/node/node*
        node_paths = glob.glob("/sys/devices/system/node/node*")
        
        if not node_paths:
            # 如果是非 NUMA 机器或无法读取，假设所有 CPU 都在 node 0
            topology[0] = set(range(psutil.cpu_count()))
            return topology

        for node_path in node_paths:
            try:
                node_id = int(os.path.basename(node_path).replace("node", ""))
                cpulist_path = os.path.join(node_path, "cpulist")
                with open(cpulist_path, 'r') as f:
                    content = f.read().strip()
                    topology[node_id] = self._parse_cpulist(content)
            except Exception as e:
                logging.warning(f"Error reading topology for {node_path}: {e}")
        return topology

    def _parse_cpulist(self, cpulist_str: str) -> Set[int]:
        """
        解析 CPU 列表字符串 (例如: "0-3,5,7-9")
        """
        cpus = set()
        if not cpulist_str:
            return cpus
        parts = cpulist_str.split(',')
        for part in parts:
            if '-' in part:
                start, end = map(int, part.split('-'))
                cpus.update(range(start, end + 1))
            else:
                cpus.add(int(part))
        return cpus

    def _format_cpulist(self, cpus: Set[int]) -> str:
        """
        将 CPU 集合格式化为字符串 (例如: {0,1,2} -> "0-2")
        """
        if not cpus:
            return ""
        sorted_cpus = sorted(list(cpus))
        ranges = []
        for cpu in sorted_cpus:
            if not ranges or cpu > ranges[-1][-1] + 1:
                ranges.append([cpu])
            else:
                ranges[-1].append(cpu)
        return ",".join(["-".join(map(str, (r[0], r[-1]))) if len(r) > 1 else str(r[0]) for r in ranges])

    # -------------------------------------------------------------------------
    # 功能 1: 监测 NUMA 整体 CPU 利用率
    # -------------------------------------------------------------------------
    def get_numa_cpu_usage(self) -> Dict[int, float]:
        """
        获取各个 NUMA 节点的 CPU 利用率，并按利用率从高到低排序返回
        返回格式: {node_id: usage_percent}
        """
        # 获取每个核心的利用率
        per_cpu_percent = psutil.cpu_percent(interval=self.interval, percpu=True)
        
        numa_usage = {}
        for node, cpus in self.numa_topology.items():
            total_usage = 0.0
            valid_cpu_count = 0
            for cpu_idx in cpus:
                if cpu_idx < len(per_cpu_percent):
                    total_usage += per_cpu_percent[cpu_idx]
                    valid_cpu_count += 1
            
            if valid_cpu_count > 0:
                numa_usage[node] = total_usage / valid_cpu_count
            else:
                numa_usage[node] = 0.0
        
        # 按利用率降序排序（为了后续逻辑，这里返回字典，但打印时可以体现排序）
        sorted_usage = dict(sorted(numa_usage.items(), key=lambda item: item[1], reverse=True))
        return sorted_usage

    # -------------------------------------------------------------------------
    # 功能 2: 监测 Cgroup 利用率 (仅限绑定在单 NUMA 内的容器)
    # -------------------------------------------------------------------------
    def _read_cgroup_cpu_nanos(self, cgroup_path: str) -> int:
        """读取 cpuacct.usage 获取总纳秒数"""
        if cgroup_path.startswith('/'):
            cgroup_path = cgroup_path[1:]
        path = os.path.join(self.cpuacct_root, cgroup_path, "cpuacct.usage")
        try:
            with open(path, 'r') as f:
                return int(f.read().strip())
        except:
            return 0

    def _get_cgroup_cpuset(self, cgroup_path: str) -> Set[int]:
        """读取 cpuset.cpus"""
        if cgroup_path.startswith('/'):
            cgroup_path = cgroup_path[1:]
        path = os.path.join(self.cpuset_root, cgroup_path, "cpuset.cpus")
        try:
            with open(path, 'r') as f:
                return self._parse_cpulist(f.read().strip())
        except:
            return set()

    def get_cgroup_metrics(self, cgroup_list) -> List[Dict]:
        """
        扫描 Docker 容器 (假设在 /docker 下) 或其他 cgroup，计算利用率。
        仅返回绑定在单个 NUMA 节点内的 Cgroup。
        """
        cgroup_metrics = []
        
        # 这里假设我们要扫描 cpuset 根目录下的直接子目录（通常是容器 ID）
        # 实际生产路径可能是 /sys/fs/cgroup/cpuset/docker/CONTAINER_ID
        # 这里为了演示，搜索 cpuset 根目录下的第一级目录
        candidate_paths = cgroup_list
        
        # 第一次采样
        start_stats = {}
        for cg in candidate_paths:
            start_stats[cg] = self._read_cgroup_cpu_nanos(cg)
            
        time.sleep(self.interval) # 必须有时间间隔才能计算利用率
        
        # 第二次采样与计算
        for cg in candidate_paths:
            end_nanos = self._read_cgroup_cpu_nanos(cg)
            start_nanos = start_stats.get(cg, 0)
            
            delta_nanos = end_nanos - start_nanos
            if delta_nanos < 0: delta_nanos = 0
            
            # CPU 利用率 = (delta_ns / (interval_sec * 1e9)) * 100 * 核心数修正? 
            # 通常 cgroup usage 是所有核的总和。
            # 这里我们计算绝对百分比（例如占用了 2.5 个核 -> 250%）
            usage_percent = (delta_nanos / (self.interval * 1_000_000_000)) * 100
            
            # 检查绑核范围
            assigned_cpus = self._get_cgroup_cpuset(cg)
            if not assigned_cpus:
                continue

            # 确定所属 NUMA
            involved_numas = set()
            for cpu in assigned_cpus:
                if cpu in self.cpu_to_numa:
                    involved_numas.add(self.cpu_to_numa[cpu])
            
            # 只有当容器完全位于一个 NUMA 节点内时才纳入管理
            if len(involved_numas) == 1:
                numa_id = list(involved_numas)[0]
                cgroup_metrics.append({
                    "name": cg,
                    "usage": usage_percent,
                    "numa_node": numa_id,
                    "cpus": assigned_cpus
                })
        
        return cgroup_metrics
    
    def get_numa_cpu_count(self, node_id: int) -> int:
        """
        获取指定 NUMA 节点的 CPU 数量
        :param node_id: NUMA 节点 ID (例如 0, 1)
        :return: 该节点的 CPU 核心数量
        """
        # self.numa_topology 结构为 {node_id: {cpu_id, ...}}
        if node_id in self.numa_topology:
            return len(self.numa_topology[node_id])
        else:
            logging.warning(f"NUMA node {node_id} not found in topology.")
            return 0

    def get_numa_load(self):
        numa_usages = self.get_numa_cpu_usage() # {node: % usage}
        if len(numa_usages) < 2:
            logging.info("Single NUMA node detected. No balancing needed.")
            return None, None

        # 计算平均负载
        avg_load = sum(numa_usages.values()) / len(numa_usages)
        logging.info(f"NUMA Load: {numa_usages}, Average Load: {avg_load:.2f}%")
        
        return numa_usages, avg_load

    # -------------------------------------------------------------------------
    # 功能 3: 负载均衡迁移
    # -------------------------------------------------------------------------
    def balance_load(self, cgroup_list):
        """
        执行核心逻辑：将高负载 NUMA 的容器迁移到低负载 NUMA
        """        
        # 1. 获取当前状态
        numa_usages, avg_load = self.get_numa_load()
        if not numa_usages:
            return
        cgroups = self.get_cgroup_metrics(cgroup_list)     # list of dicts
        numa_cpu_num = self.get_numa_cpu_count(0)

        # 将 Cgroup 按所属 NUMA 分组
        numa_cgroups: Dict[int, List[Dict]] = {node: [] for node in numa_usages}
        for cg in cgroups:
            if cg['numa_node'] in numa_cgroups:
                numa_cgroups[cg['numa_node']].append(cg)
        
        # 对每个节点内的 cgroup 按利用率降序排序，方便优先迁移大负载
        for node in numa_cgroups:
            numa_cgroups[node].sort(key=lambda x: x['usage'], reverse=True)

        # 2. 识别源节点(高负载) 和 目标节点(低负载)
        # 阈值：只有偏差超过 10% 才考虑迁移，防止抖动
        tolerance = 10.0 
        
        sorted_nodes = sorted(numa_usages.keys(), key=lambda n: numa_usages[n], reverse=True)
        # 简单贪心算法：尝试从负载最高的节点搬运到负载最低的节点
        
        # 虚拟状态，用于模拟迁移后的负载变化
        virtual_load = numa_usages.copy()
        moves = []

        # 迭代尝试迁移
        # 为了简化，我们只做一轮匹配：高 -> 低
        high_idx = 0
        low_idx = len(sorted_nodes) - 1

        while high_idx < low_idx:
            src_node = sorted_nodes[high_idx]
            dst_node = sorted_nodes[low_idx]

            # 如果源节点负载已经不高，或者目标节点负载已经不低，停止
            if virtual_load[src_node] <= avg_load + tolerance:
                high_idx += 1
                continue
            if virtual_load[dst_node] >= avg_load - tolerance:
                low_idx -= 1
                continue

            # 尝试在 src_node 中找到一个合适的容器迁移到 dst_node
            # 最佳容器：Usage < (src_current - avg) 且 Usage < (avg - dst_current)
            # 即：能填补低谷，且不会把低谷变成高峰，同时能削峰
            
            moved_cg = None
            for cg in numa_cgroups[src_node]:
                cg_usage = cg['usage']
                # 预判迁移后的情况，判断条件：源节点CPU利用率>=50，迁移后目标节点CPU利用率小于90，源节点大于10
                if virtual_load[src_node] >= 40 and \
                   (virtual_load[dst_node] + cg_usage / numa_cpu_num < 90) and \
                   (virtual_load[src_node] - cg_usage / numa_cpu_num > 10):
                    
                    moved_cg = cg
                    break
            
            if moved_cg:
                # 记录迁移决策
                moves.append((moved_cg, src_node, dst_node))
                
                # 更新虚拟状态
                virtual_load[src_node] -= moved_cg['usage']
                virtual_load[dst_node] += moved_cg['usage']
                
                # 从待选列表移除，防止重复计算
                numa_cgroups[src_node].remove(moved_cg)
                logging.info(f"Plan to move {moved_cg['name']} (Load: {moved_cg['usage']:.1f}%) "
                      f"from Node {src_node} -> Node {dst_node}")
            else:
                # 当前配对无法找到合适的容器，放弃这对组合中的一个
                # 通常放弃高负载的那个（因为已经找不到可搬运的了），尝试下一个高负载
                high_idx += 1

        # 3. 执行迁移
        logging.info(f"Planned {len(moves)} migrations.")
        for cg, src, dst in moves:
            self.migrate_cgroup(cg['name'], dst)
        
        return moves

    def migrate_cgroup(self, cgroup_name: str, target_numa_node: int):
        """
        执行实际迁移：修改 cpuset.cpus
        """
        # 获取目标 NUMA 的所有 CPU
        target_cpus = self.numa_topology.get(target_numa_node, set())
        if not target_cpus:
            logging.warning(f"Target NUMA {target_numa_node} has no CPUs.")
            return

        cpulist_str = self._format_cpulist(target_cpus)
        if cgroup_name.startswith('/'):
            cgroup_name = cgroup_name[1:]

        path = os.path.join(self.cpuset_root, cgroup_name, "cpuset.cpus")
        
        logging.info(f"Migrating {cgroup_name} to NUMA {target_numa_node} (CPUs: {cpulist_str})")
        
        # 安全检查：确保路径存在且安全
        if not os.path.exists(path):
            logging.warning(f"Path not found: {path}")
            return
            
        try:
            # 写入新的 CPU 列表
            with open(path, 'w') as f:
                f.write(cpulist_str)
                f.flush()
            
            # 同时需要更新 cpuset.mems 以确保内存亲和性（通常必须与 cpuset.cpus 匹配）
            mems_path = os.path.join(self.cpuset_root, cgroup_name, "cpuset.mems")
            if os.path.exists(mems_path):
                with open(mems_path, 'w') as f:
                    f.write(str(target_numa_node))
                    
            logging.info(f"Success {cgroup_name} migrated.")
            
        except PermissionError:
            logging.warning("Permission denied. Please run as root.")
        except Exception as e:
            logging.warning(f"Failed to migrate: {e}")


if __name__ == "__main__":
    transfer = NumaTransfer(interval=1.0)
    
    # 运行一次负载均衡
    try:
        _ = transfer.balance_load()
    except KeyboardInterrupt:
        logging.info("Stopped.")