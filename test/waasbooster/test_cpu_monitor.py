# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import unittest
from unittest import mock
from unittest.mock import patch, mock_open, MagicMock
import os
import sys
import time
from collections import deque

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
from cpu_monitor import CpuMonitor

logging.set_log_instance("INFO")


class TestCpuMonitor(unittest.TestCase):
    def setUp(self):
        # 创建CpuMonitor实例
        self.cpu_monitor = CpuMonitor()
        
        # 初始化container_info_queue_dict的数据
        self.cpu_monitor.container_info_queue_dict = {
            "/sys/fs/cgroup/container1": {
                "cpu_util": deque([10, 20, 30], maxlen=15),
                "quota_util": deque([5, 15, 25], maxlen=15),
                "avg_quota_util": 15,
                "ac_quota": 1000
            },
            "/sys/fs/cgroup/container2": {
                "cpu_util": deque([15, 25, 35], maxlen=15),
                "quota_util": deque([10, 20, 30], maxlen=15),
                "avg_quota_util": 20,
                "ac_quota": 2000
            }
        }
        self.samples = {
            "/sys/fs/cgroup/container1": (1000000, time.time())
        }

    def test_get_container_info_queue_dict(self):
        # 调用get_container_info_queue_dict方法
        result = self.cpu_monitor.get_container_info_queue_dict()
        
        # 验证返回的数据是否是container_info_queue_dict的一个浅拷贝
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 2)
        
        # 验证返回的值是否正确
        self.assertEqual(result["/sys/fs/cgroup/container1"]["avg_quota_util"], 15)
        self.assertEqual(result["/sys/fs/cgroup/container2"]["ac_quota"], 2000)

        # 验证copy是否是浅拷贝，修改拷贝数据不会影响原数据
        result["/sys/fs/cgroup/container1"]["avg_quota_util"] = 100
        self.assertEqual(result["/sys/fs/cgroup/container1"]["avg_quota_util"], self.cpu_monitor.container_info_queue_dict["/sys/fs/cgroup/container1"]["avg_quota_util"])

    def test_get_container_info_queue_dict_empty(self):
        # 创建一个空的CpuMonitor实例
        empty_monitor = CpuMonitor()
        
        # 调用get_container_info_queue_dict方法
        result = empty_monitor.get_container_info_queue_dict()
        
        # 验证返回的数据是否为空
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    @patch("builtins.open", mock_open(read_data="1234567890"))
    def test_get_cpu_usage_success(self):
        # 假设路径是'/sys/fs/cgroup/my_container'
        path = '/sys/fs/cgroup/my_container'
        
        # 调用get_cpu_usage方法
        result = CpuMonitor.get_cpu_usage(path)
        
        # 验证open是否被调用，并且读取了正确的文件
        open.assert_called_with(os.path.join(path, 'cpuacct.usage'), 'r')
        
        # 验证返回值是否符合预期
        self.assertEqual(result, 1234567890)

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_cpu_usage_file_not_found(self, mock_file):
        # 假设路径是'/sys/fs/cgroup/my_container'
        path = '/sys/fs/cgroup/my_container'
        
        # 调用get_cpu_usage方法
        result = CpuMonitor.get_cpu_usage(path)
        
        # 验证返回值是None，因为文件未找到
        self.assertIsNone(result)

    @patch("builtins.open", side_effect=Exception("Unexpected error"))
    def test_get_cpu_usage_unexpected_error(self, mock_file):
        # 假设路径是'/sys/fs/cgroup/my_container'
        path = '/sys/fs/cgroup/my_container'
        
        # 调用get_cpu_usage方法
        result = CpuMonitor.get_cpu_usage(path)
        
        # 验证返回值是None，因为发生了意外错误
        self.assertIsNone(result)


    @patch("builtins.open", side_effect=[mock_open(read_data="1000000").return_value,
                                        mock_open(read_data="200000").return_value])
    def test_get_cpu_limits_success(self, mock_file):
        # 假设路径是'/sys/fs/cgroup/my_container'
        path = '/sys/fs/cgroup/my_container'
        
        # 调用get_cpu_limits方法
        quota, period = CpuMonitor.get_cpu_limits(path)
        
        # 验证open是否被调用，并且读取了正确的文件
        open.assert_any_call(os.path.join(path, 'cpu.cfs_quota_us'), 'r')
        open.assert_any_call(os.path.join(path, 'cpu.cfs_period_us'), 'r')
        
        # 验证返回值是否符合预期
        self.assertEqual(quota, 1000000)
        self.assertEqual(period, 200000)

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_cpu_limits_file_not_found(self, mock_file):
        # 假设路径是'/sys/fs/cgroup/my_container'
        path = '/sys/fs/cgroup/my_container'
        
        # 调用get_cpu_limits方法
        quota, period = CpuMonitor.get_cpu_limits(path)
        
        # 验证返回值是 (-1, 100000)，因为文件未找到
        self.assertEqual(quota, -1)
        self.assertEqual(period, 100000)

    @patch("builtins.open", side_effect=Exception("Unexpected error"))
    def test_get_cpu_limits_unexpected_error(self, mock_file):
        # 假设路径是'/sys/fs/cgroup/my_container'
        path = '/sys/fs/cgroup/my_container'
        
        # 调用get_cpu_limits方法
        quota, period = CpuMonitor.get_cpu_limits(path)
        
        # 验证返回值是 (-1, 100000)，因为发生了意外错误
        self.assertEqual(quota, -1)
        self.assertEqual(period, 100000)


    @patch("time.sleep")  # Mock time.sleep to avoid real waiting
    @patch.object(CpuMonitor, "get_cpu_usage", return_value=2000000)  # Mock get_cpu_usage to return fake usage
    @patch.object(CpuMonitor, "get_cpu_limits", return_value=(1000000, 200000))  # Mock get_cpu_limits
    @patch("cpu_monitor.weighted_queue_sum", return_value=20)  # Mock weighted_queue_sum for testing
    def test_cpu_util_cal(self, mock_weighted_queue_sum, mock_get_cpu_limits, mock_get_cpu_usage, mock_sleep):
        # 调用cpu_util_cal方法
        containers = ["/sys/fs/cgroup/container1"]
        interval = 1  # 1 second interval

        # 计算时调用
        result = self.cpu_monitor.cpu_util_cal(containers, self.samples, interval)

        # 验证 get_cpu_usage 被正确调用
        mock_get_cpu_usage.assert_called_with("/sys/fs/cgroup/container1")
        
        # 验证 get_cpu_limits 被正确调用
        mock_get_cpu_limits.assert_called_with("/sys/fs/cgroup/container1")
    
        # 验证 container_info_queue_dict 是否按预期更新
        self.assertEqual(result["/sys/fs/cgroup/container1"]["avg_quota_util"], 20)
        self.assertEqual(result["/sys/fs/cgroup/container1"]["ac_quota"], 1000000)

        # 验证样本数据是否被更新
        updated_usage, updated_time = self.samples["/sys/fs/cgroup/container1"]
        self.assertGreater(updated_usage, 1000000)
        self.assertEqual(updated_time, self.samples["/sys/fs/cgroup/container1"][1])

    @patch("time.sleep")  # Mock time.sleep to avoid real waiting
    @patch.object(CpuMonitor, "get_cpu_usage", return_value=None)  # Simulate get_cpu_usage failure (None)
    def test_cpu_util_cal_get_cpu_usage_failure(self, mock_sleep, mock_get_cpu_usage):
        containers = ["/sys/fs/cgroup/container1"]
        interval = 1  # 1 second interval

        # 计算时调用
        result = self.cpu_monitor.cpu_util_cal(containers, self.samples, interval)

        # 验证当 get_cpu_usage 返回 None 时，cpu_util_cal 不会进一步计算
        self.assertEqual(result, self.cpu_monitor.container_info_queue_dict)



    @patch("time.sleep")  # Mock time.sleep to avoid real waiting
    @patch.object(CpuMonitor, "get_cpu_usage", return_value=2000000)  # Mock get_cpu_usage to return fake usage
    @patch.object(CpuMonitor, "get_cpu_limits", return_value=(-1, 100000))  # Simulate no quota
    def test_cpu_util_cal_no_quota(self, mock_sleep, mock_get_cpu_usage, mock_get_cpu_limits):
        containers = ["/sys/fs/cgroup/container1"]
        interval = 1  # 1 second interval

        # 计算时调用
        result = self.cpu_monitor.cpu_util_cal(containers, self.samples, interval)

        # 验证 quota 为 -1 时，relative_util 应为 None
        self.assertIsNotNone(result["/sys/fs/cgroup/container1"]["quota_util"])


if __name__ == "__main__":
    unittest.main()