"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent sample test
"""

import unittest
from unittest import mock
from unittest.mock import patch, mock_open, MagicMock
import os
import sys
import time
from collections import deque

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/agent"))

import sample

class TestSample(unittest.TestCase):
    def setUp(self):
        self.counter = sample.PerfCount()
        super().setUp()


    def multi_open(self):
        try:
            counter1 = sample.PerfCount()
        except Exception as e:
            self.assertIsInstance(e, ValueError)


    def test_count(self):
        result = self.counter.count(1)

        # 验证返回的数据可读
        self.assertIsNotNone(result)

        data = self.counter.get_data()

        # 验证包含时间戳
        self.assertIsNotNone(data["start_time"])
        self.assertIsNotNone(data["stop_time"])

        # 验证包含统计值
        for _, cpu_data in data['all'].items():
            self.assertIsNotNone(cpu_data['INST_RETIRED'])
            self.assertIsNotNone(cpu_data['CPU_CYCLES'])
            self.assertIsNotNone(cpu_data['BR_RETIRED'])
            self.assertIsNotNone(cpu_data['BR_MIS_PRED_RETIRED'])
            self.assertIsNotNone(cpu_data['LL_CACHE'])
            self.assertIsNotNone(cpu_data['LL_CACHE_MISS'])
            self.assertIsNotNone(cpu_data['INST_SPEC'])
            self.assertIsNotNone(cpu_data['LD_SPEC'])
            self.assertIsNotNone(cpu_data['ST_SPEC'])
            self.assertIsNotNone(cpu_data['LDREX_SPEC'])
            self.assertIsNotNone(cpu_data['STREX_SPEC'])
            self.assertIsNotNone(cpu_data['INT_SPEC'])
            self.assertIsNotNone(cpu_data['FP_SPEC'])
            self.assertIsNotNone(cpu_data['SIMD_INST_SPEC'])
            self.assertIsNotNone(cpu_data['ASE_INST_SPEC'])
            self.assertIsNotNone(cpu_data['SVE_INST_SPEC'])
            self.assertIsNotNone(cpu_data['SME_INST_SPEC'])

            self.assertIsNotNone(cpu_data['L1I_CACHE'])
            self.assertIsNotNone(cpu_data['L1I_CACHE_REFILL'])
            self.assertIsNotNone(cpu_data['L1D_CACHE'])
            self.assertIsNotNone(cpu_data['L1D_CACHE_REFILL'])
            self.assertIsNotNone(cpu_data['L1I_TLB'])
            self.assertIsNotNone(cpu_data['L1I_TLB_REFILL'])

            self.assertIsNotNone(cpu_data['L2I_CACHE'])
            self.assertIsNotNone(cpu_data['L2I_CACHE_REFILL'])
            self.assertIsNotNone(cpu_data['L2D_CACHE'])
            self.assertIsNotNone(cpu_data['L2D_CACHE_REFILL'])
            self.assertIsNotNone(cpu_data['L2I_TLB'])
            self.assertIsNotNone(cpu_data['L2I_TLB_REFILL'])

            self.assertIsNotNone(cpu_data['L1D_TLB'])
            self.assertIsNotNone(cpu_data['L1D_TLB_REFILL'])
            self.assertIsNotNone(cpu_data['L2D_TLB'])
            self.assertIsNotNone(cpu_data['L2D_TLB_REFILL'])
            self.assertIsNotNone(cpu_data['IRQ:IRQ_HANDLER_ENTRY'])
            self.assertIsNotNone(cpu_data['IRQ:SOFTIRQ_ENTRY'])

            self.assertIsNotNone(cpu_data['MAJOR-FAULTS'])
            self.assertIsNotNone(cpu_data['MINOR-FAULTS'])
            self.assertIsNotNone(cpu_data['PAGE-FAULTS'])
            self.assertIsNotNone(cpu_data['TASK-CLOCK'])
            self.assertIsNotNone(cpu_data['CPU-CLOCK'])
            self.assertIsNotNone(cpu_data['CONTEXT-SWITCHES'])


if __name__ == "__main__":
    unittest.main()