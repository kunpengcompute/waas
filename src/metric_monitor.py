# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025


import time
import copy
import threading
import argparse
import kperf
from collections import defaultdict

import util
import waas_log as logging



class MetricMonitor:
    """
    用于对多个 Linux cgroup 统计 TLB Miss Rate 的监控类
    """

    def __init__(self, evtList):
        """
        evtList: 监控的 PMU 事件，例如：
            [
                "l1d_tlb_refill", "l1d_tlb",
                "l1i_tlb_refill", "l1i_tlb",
                "l2d_tlb_refill", "l2d_tlb",
                "l2i_tlb_refill", "l2i_tlb"
            ]
        """
        self.evtList = evtList
        self.pd = None
        self.cgroup_info_dict = {}
        self.lock = threading.Lock()
        self.running = True

    def _safe_div(self, a, b):
        return a / b if b else 0.0

    def _compute_rates(self, evt_map):
        """
        输入：{ cgroup: {evt: count} }
        输出 miss-rate 结构
        """
        mapping = {
            "l1d": ("l1d_tlb_refill", "l1d_tlb"),
            "l1i": ("l1i_tlb_refill", "l1i_tlb"),
            "l2d": ("l2d_tlb_refill", "l2d_tlb"),
            "l2i": ("l2i_tlb_refill", "l2i_tlb"),
        }

        result = {}

        for cgroup, counts in evt_map.items():
            rates = {}
            for level, (miss_evt, access_evt) in mapping.items():
                miss = counts.get(miss_evt, 0)
                access = counts.get(access_evt, 0)
                rates[level] = {
                    "miss_rate": self._safe_div(miss, access)
                }

            result[cgroup] = rates

        return result

    def collect_once(self, cgroup_list, duration=1.0):
        """
        启动一次采集，自动完成：
        enable -> sleep -> disable -> read -> 计算 miss rate

        return: miss-rate 字典
        """
        # 打开 PMU
        pmu_attr = kperf.PmuAttr(evtList=self.evtList,
                                 cgroupNameList=cgroup_list)

        self.pd = kperf.open(kperf.PmuTaskType.COUNTING, pmu_attr)
        if self.pd == -1:
            raise RuntimeError(f"kperf open failed: {kperf.error()}")

        # 采集
        kperf.enable(self.pd)
        time.sleep(duration)
        kperf.disable(self.pd)

        # 读取
        raw = defaultdict(lambda: defaultdict(int))
        pmu_data = kperf.read(self.pd)

        for item in pmu_data.iter:
            raw[item.cgroupName][item.evt] += item.count

        # 关闭 pmu event
        kperf.close(self.pd)
        self.pd = None

        # 计算 miss rate
        return self._compute_rates(raw)

    def run(self, cgroup_list, monitor_interval):
        if not cgroup_list:
            logging.info('No cgroup to find.')
            return
        pmu_attr = kperf.PmuAttr(evtList=self.evtList,
                                 cgroupNameList=cgroup_list)

        self.pd = kperf.open(kperf.PmuTaskType.COUNTING, pmu_attr)
        if self.pd == -1:
            raise RuntimeError(f"kperf open failed: {kperf.error()}")
        try:
            while self.running:
                kperf.enable(self.pd)
                time.sleep(monitor_interval)
                kperf.disable(self.pd)
                raw = defaultdict(lambda: defaultdict(int))
                pmu_data = kperf.read(self.pd)

                for item in pmu_data.iter:
                    raw[item.cgroupName][item.evt] += item.count
                self.cgroup_info_dict = self._compute_rates(raw)
            logging.debug("Waas monitor stoped.")
        except Exception as e:
            logging.warning('kperf failed for: %s', e)
        finally:
            if self.pd is not None:
                kperf.close(self.pd)
                self.pd = None
    
    def stop(self):
        self.running = False

    def get_monitor_cgroup_metric(self):
        with self.lock:
            cgroup_info_dict = copy.copy(self.cgroup_info_dict)
        return cgroup_info_dict