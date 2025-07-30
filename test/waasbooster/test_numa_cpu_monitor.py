# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys
import time
from collections import deque
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
from numa_cpu_monitor import NUMAMonitor


class TestNUMAMonitor(unittest.TestCase):

    def test_parse_cpu_range_single_cpu(self):
        result = NUMAMonitor.parse_cpu_range("0")
        self.assertEqual(result, [0])

    def test_parse_cpu_range_range(self):
        result = NUMAMonitor.parse_cpu_range("0-3")
        self.assertEqual(result, [0, 1, 2, 3])

    def test_parse_cpu_range_mixed(self):
        result = NUMAMonitor.parse_cpu_range("0-1,3")
        self.assertEqual(result, [0, 1, 3])

    def test_get_numa_cpu_mapping_no_sys_node_path(self):
        # Mocking util.SYS_NODE_PATH to simulate non-existence of the path
        with patch('util.SYS_NODE_PATH', '/nonexistent/path'):
            monitor = NUMAMonitor()
            with self.assertRaises(Exception) as context:
                monitor.get_numa_cpu_mapping()
            self.assertTrue('NUMA not supported or /sys not accessible' in str(context.exception))

    @patch("os.listdir")
    @patch("builtins.open", new_callable=mock_open, read_data="0-3")
    def test_get_numa_cpu_mapping(self, mock_file, mock_listdir):
        mock_listdir.return_value = ['node0', 'node1']
        monitor = NUMAMonitor()
        numa_cpus = monitor.get_numa_cpu_mapping()
        
        # Check that the method returns the expected mapping
        self.assertEqual(numa_cpus, {0: [0, 1, 2, 3], 1: [0, 1, 2, 3]})
        mock_file.assert_called_with('/sys/devices/system/node/node1/cpulist', 'r')

    @patch("builtins.open", new_callable=mock_open, read_data="cpu  100 100 100 100 100 100 100 100 100 100")
    def test_get_numa_cpu_dict(self, mock_file):
        monitor = NUMAMonitor()
        numa_dict = monitor.get_numa_cpu_dict()
        self.assertIsInstance(numa_dict, dict)

    @patch.object(NUMAMonitor, 'get_cpu_utilization')
    def test_update_numa_util_dict(self, mock_get_cpu_utilization):
        # 设置 mock 返回的 CPU 利用率
        mock_get_cpu_utilization.return_value = {
            0: 50.0,
            1: 60.0,
            2: 70.0,
            3: 80.0
        }
        
        # 创建 NUMAMonitor 实例
        monitor = NUMAMonitor(queue_max_len=3)
        
        # 设置初始 numa_util_dict 内容
        monitor.numa_util_dict = {
            'all': deque([0.0, 0.0], maxlen=3),
            0: deque([0.0, 0.0], maxlen=3),
            1: deque([0.0, 0.0], maxlen=3)
        }
        
        # 设置 NUMA CPU 映射
        numa_cpus = {
            0: [0, 1],
            1: [2, 3]
        }
        
        # 调用 update_numa_util_dict
        updated_dict = monitor.update_numa_util_dict(numa_cpus)
        
        # 检查 `numa_util_dict` 是否更新正确
        self.assertEqual(updated_dict['all'][-1], 65.0)  # all 的平均值 (50 + 60 + 70 + 80) / 4 = 65.0
        self.assertEqual(updated_dict[0][-1], 55.0)  # 节点 0 的平均值 (50 + 60) / 2 = 55.0
        self.assertEqual(updated_dict[1][-1], 75.0)  # 节点 1 的平均值 (70 + 80) / 2 = 75.0
        
        # 检查队列长度
        self.assertEqual(len(updated_dict['all']), 3)  # 队列长度应该限制为 3
        self.assertEqual(len(updated_dict[0]), 3)      # 队列长度应该限制为 3
        self.assertEqual(len(updated_dict[1]), 3)      # 队列长度应该限制为 3

    @patch.object(NUMAMonitor, 'get_cpu_utilization')
    def test_update_numa_util_dict_with_empty_cpu_utils(self, mock_get_cpu_utilization):
        # 设置 mock 返回的 CPU 利用率为空
        mock_get_cpu_utilization.return_value = {}
        
        # 创建 NUMAMonitor 实例
        monitor = NUMAMonitor(queue_max_len=3)
        
        # 设置初始 numa_util_dict 内容
        monitor.numa_util_dict = {
            'all': deque([0.0, 0.0], maxlen=3),
            0: deque([0.0, 0.0], maxlen=3),
            1: deque([0.0, 0.0], maxlen=3)
        }
        
        # 设置 NUMA CPU 映射
        numa_cpus = {
            0: [0, 1],
            1: [2, 3]
        }
        
        # 调用 update_numa_util_dict
        updated_dict = monitor.update_numa_util_dict(numa_cpus)
        
        # 检查 `numa_util_dict` 是否更新正确
        self.assertEqual(updated_dict['all'][-1], 0.0)  # all 的平均值应该是 0.0 (因为 cpu_utils 为空)
        self.assertEqual(updated_dict[0][-1], 0.0)      # 节点 0 的平均值应该是 0.0
        self.assertEqual(updated_dict[1][-1], 0.0)      # 节点 1 的平均值应该是 0.0
        
        # 检查队列长度
        self.assertEqual(len(updated_dict['all']), 3)  # 队列长度应该限制为 3
        self.assertEqual(len(updated_dict[0]), 3)      # 队列长度应该限制为 3
        self.assertEqual(len(updated_dict[1]), 3)      # 队列长度应该限制为 3

    @patch.object(NUMAMonitor, 'get_cpu_utilization')
    def test_update_numa_util_dict_with_exception(self, mock_get_cpu_utilization):
        # 设置 mock 抛出异常
        mock_get_cpu_utilization.side_effect = Exception("Error in CPU Utilization")
        
        # 创建 NUMAMonitor 实例
        monitor = NUMAMonitor(queue_max_len=3)
        
        # 设置初始 numa_util_dict 内容
        monitor.numa_util_dict = {
            'all': deque([0.0, 0.0], maxlen=3),
            0: deque([0.0, 0.0], maxlen=3),
            1: deque([0.0, 0.0], maxlen=3)
        }
        
        # 设置 NUMA CPU 映射
        numa_cpus = {
            0: [0, 1],
            1: [2, 3]
        }
        
        # 调用 update_numa_util_dict 并检查异常处理
        with self.assertRaises(Exception):
            monitor.update_numa_util_dict(numa_cpus)

    @patch("builtins.open", new_callable=mock_open)
    @patch("time.sleep", return_value=None)  # Mock sleep to avoid delays
    def test_get_cpu_utilization(self, mock_sleep, mock_file):
        # 模拟 /proc/stat 内容
        mock_file.return_value.readlines.return_value = [
            "cpu  123 123 123 123 123 123 123 123 123 123\n",
            "cpu0 100 100 100 100 100 100 100 100 100 100\n",
            "cpu1 110 110 110 110 110 110 110 110 110 110\n"
        ]

        # 模拟 _parse_stat_line 方法
        def mock_parse_stat_line(line):
            return {
                'total': sum(map(int, line.split()[1:8])),
                'idle': int(line.split()[4])
            }

        # 使用 mock_parse_stat_line 模拟 _parse_stat_line
        with patch.object(NUMAMonitor, '_parse_stat_line', side_effect=mock_parse_stat_line):
            monitor = NUMAMonitor()
            cpu_utilization = monitor.get_cpu_utilization(interval=1)

            # 验证 get_cpu_utilization 返回的 CPU 利用率
            self.assertEqual(cpu_utilization, {0: 0.0, 1: 0.0})  # 示例数据，计算公式根据行数据

    @patch("builtins.open", new_callable=mock_open)
    @patch("time.sleep", return_value=None)  # Mock sleep to avoid delays
    def test_get_cpu_utilization_with_zero_total_diff(self, mock_sleep, mock_file):
        # 模拟 /proc/stat 内容，测试 total_diff 为零的情况
        mock_file.return_value.readlines.return_value = [
            "cpu  100 100 100 100 100 100 100 100 100 100\n",
            "cpu0 100 100 100 100 100 100 100 100 100 100\n",
            "cpu1 100 100 100 100 100 100 100 100 100 100\n"
        ]

        # 模拟 _parse_stat_line 方法
        def mock_parse_stat_line(line):
            return {
                'total': sum(map(int, line.split()[1:8])),
                'idle': int(line.split()[4])
            }

        # 使用 mock_parse_stat_line 模拟 _parse_stat_line
        with patch.object(NUMAMonitor, '_parse_stat_line', side_effect=mock_parse_stat_line):
            monitor = NUMAMonitor()
            cpu_utilization = monitor.get_cpu_utilization(interval=1)

            # 验证 get_cpu_utilization 返回的 CPU 利用率
            self.assertEqual(cpu_utilization, {0: 0.0, 1: 0.0})  # 示例数据，total_diff 为零时利用率为 0

    @patch("builtins.open", new_callable=mock_open)
    @patch("time.sleep", return_value=None)  # Mock sleep to avoid delays
    def test_get_cpu_utilization_with_no_cpu(self, mock_sleep, mock_file):
        # 模拟 /proc/stat 内容，没有任何 CPU 信息
        mock_file.return_value.readlines.return_value = [
            "cpu  0 0 0 0 0 0 0 0 0 0\n"
        ]

        # 模拟 _parse_stat_line 方法
        def mock_parse_stat_line(line):
            return {
                'total': sum(map(int, line.split()[1:8])),
                'idle': int(line.split()[4])
            }

        # 使用 mock_parse_stat_line 模拟 _parse_stat_line
        with patch.object(NUMAMonitor, '_parse_stat_line', side_effect=mock_parse_stat_line):
            monitor = NUMAMonitor()
            cpu_utilization = monitor.get_cpu_utilization(interval=1)

            # 验证返回值为空字典
            self.assertEqual(cpu_utilization, {})


if __name__ == "__main__":
    unittest.main()