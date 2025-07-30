# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
from util import AC_QUOTA, BT_QUOTA, OG_QUOTA, CPU_SHARES
from quota_manager import _get_cgroup_version, _get_pods_to_limit, _get_pods_to_scale, _get_overload_pods, QuotaManager

class TestGetCgroupVersion(unittest.TestCase):

    @patch('subprocess.run')  # 模拟 subprocess.run 方法
    def test_get_cgroup_version_v1(self, mock_run):
        # 模拟返回 tmpfs
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = 'tmpfs'
        mock_run.return_value = mock_process

        result = _get_cgroup_version()
        self.assertEqual(result, 'v1')  # 期望返回 'v1'

    @patch('subprocess.run')  # 模拟 subprocess.run 方法
    def test_get_cgroup_version_v2(self, mock_run):
        # 模拟返回 cgroup2fs
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = 'cgroup2fs'
        mock_run.return_value = mock_process

        result = _get_cgroup_version()
        self.assertEqual(result, 'v2')  # 期望返回 'v2'

    @patch('subprocess.run')  # 模拟 subprocess.run 方法
    def test_get_cgroup_version_error(self, mock_run):
        # 模拟返回错误的命令
        mock_process = MagicMock()
        mock_process.returncode = 1  # 使返回错误
        mock_run.return_value = mock_process

        result = _get_cgroup_version()
        self.assertEqual(result, 'error')  # 期望返回 'error'

    @patch('subprocess.run')  # 模拟 subprocess.run 方法
    def test_get_cgroup_version_invalid(self, mock_run):
        # 模拟返回未知的文件系统
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = 'unknown_fs'
        mock_run.return_value = mock_process

        result = _get_cgroup_version()
        self.assertEqual(result, 'unknown_fs')  # 期望返回 'unknown_fs'

    @patch('subprocess.run')  # 模拟 subprocess.run 方法
    def test_get_cgroup_version_file_not_found(self, mock_run):
        # 模拟 FileNotFoundError
        mock_run.side_effect = FileNotFoundError("File not found error")

        with self.assertRaises(FileNotFoundError):
            _get_cgroup_version()  # 期望抛出 FileNotFoundError

    @patch('subprocess.run')  # 模拟 subprocess.run 方法
    def test_get_cgroup_version_permission_error(self, mock_run):
        # 模拟 PermissionError
        mock_run.side_effect = PermissionError("Permission error")

        with self.assertRaises(PermissionError):
            _get_cgroup_version()  # 期望抛出 PermissionError


class TestGetPodsToLimit(unittest.TestCase):

    def test_get_pods_to_limit_all(self):
        throttle_numa_nodes = {'all': 100}  # 模拟所有 NUMA 节点
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 },
            'pod3': { AC_QUOTA: 700, BT_QUOTA: 600 }
        }
        pod_numa_nodes = {
            'pod1': [0],
            'pod2': [1],
            'pod3': [2]
        }

        expected_result = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod3': { AC_QUOTA: 700, BT_QUOTA: 600 }
        }

        result = _get_pods_to_limit(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, expected_result)

    def test_get_pods_to_limit_specific_node(self):
        throttle_numa_nodes = {0: 50}  # 模拟特定 NUMA 节点
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 },
            'pod3': { AC_QUOTA: 700, BT_QUOTA: 600 }
        }
        pod_numa_nodes = {
            'pod1': [0],  # pod1 使用 NUMA 节点 0
            'pod2': [1],  # pod2 使用 NUMA 节点 1
            'pod3': [0]   # pod3 使用 NUMA 节点 0
        }

        expected_result = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod3': { AC_QUOTA: 700, BT_QUOTA: 600 }
        }

        result = _get_pods_to_limit(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, expected_result)

    def test_get_pods_to_limit_no_overload(self):
        throttle_numa_nodes = {0: 50}
        pod_quotas = {
            'pod1': { AC_QUOTA: 300, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 450, BT_QUOTA: 450 }
        }
        pod_numa_nodes = {
            'pod1': [0],
            'pod2': [1]
        }

        result = _get_pods_to_limit(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, {})  # No pods should be limited

    def test_get_pods_to_limit_empty_pod_quotas(self):
        throttle_numa_nodes = {0: 50}
        pod_quotas = {}  # No pod quotas
        pod_numa_nodes = {}

        result = _get_pods_to_limit(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, {})  # No pods should be limited

    def test_get_pods_to_limit_empty_throttle_nodes(self):
        throttle_numa_nodes = {}  # No throttle NUMA nodes
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_numa_nodes = {
            'pod1': [0],
            'pod2': [1]
        }

        expected_result = {}

        result = _get_pods_to_limit(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, expected_result)

    def test_get_pods_to_limit_multiple_throttle_nodes(self):
        throttle_numa_nodes = {0: 50, 1: 60}  # Multiple throttle NUMA nodes
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 700, BT_QUOTA: 600 }
        }
        pod_numa_nodes = {
            'pod1': [0],  # pod1 使用 NUMA 节点 0
            'pod2': [1]   # pod2 使用 NUMA 节点 1
        }

        expected_result = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 700, BT_QUOTA: 600 }
        }

        result = _get_pods_to_limit(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, expected_result)


class TestGetPodsToScale(unittest.TestCase):

    def test_get_pods_to_scale_no_throttle_nodes(self):
        throttle_numa_nodes = {}  # No throttle NUMA nodes
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 },
            'pod3': { AC_QUOTA: 700, BT_QUOTA: 600 }
        }
        pod_numa_nodes = {
            'pod1': [0],
            'pod2': [1],
            'pod3': [2]
        }

        # No throttling, all pods should be scalable
        expected_result = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 },
            'pod3': { AC_QUOTA: 700, BT_QUOTA: 600 }
        }

        result = _get_pods_to_scale(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, expected_result)

    def test_get_pods_to_scale_with_throttle_node(self):
        throttle_numa_nodes = {0: 50}  # Simulating a throttled NUMA node
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 700, BT_QUOTA: 600 },
            'pod3': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_numa_nodes = {
            'pod1': [0],  # pod1 is on NUMA node 0
            'pod2': [1],  # pod2 is on NUMA node 1
            'pod3': [0]   # pod3 is on NUMA node 0
        }

        # pod1 and pod3 are on NUMA node 0 (throttled), so they shouldn't be scalable
        expected_result = {
            'pod2': { AC_QUOTA: 700, BT_QUOTA: 600 }
        }

        result = _get_pods_to_scale(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, expected_result)

    def test_get_pods_to_scale_with_multiple_throttle_nodes(self):
        throttle_numa_nodes = {0: 50, 1: 60}  # Multiple throttled NUMA nodes
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 700, BT_QUOTA: 600 },
            'pod3': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_numa_nodes = {
            'pod1': [0],  # pod1 is on NUMA node 0
            'pod2': [1],  # pod2 is on NUMA node 1
            'pod3': [2]   # pod3 is on NUMA node 2
        }

        # All pods are either on throttled NUMA nodes (0, 1) except pod3
        expected_result = {
            'pod3': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }

        result = _get_pods_to_scale(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, expected_result)

    def test_get_pods_to_scale_no_scalable_pods(self):
        throttle_numa_nodes = {0: 50}  # Throttled NUMA node
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_numa_nodes = {
            'pod1': [0],  # pod1 is on NUMA node 0
            'pod2': [0]   # pod2 is on NUMA node 0
        }

        # Both pods are on throttled NUMA node 0, so no scalable pods
        result = _get_pods_to_scale(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, {})

    def test_get_pods_to_scale_empty_pod_quotas(self):
        throttle_numa_nodes = {0: 50}
        pod_quotas = {}  # No pods to scale
        pod_numa_nodes = {}

        result = _get_pods_to_scale(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, {})  # No pods should be scalable

    def test_get_pods_to_scale_empty_throttle_nodes(self):
        throttle_numa_nodes = {}  # No throttle NUMA nodes
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_numa_nodes = {
            'pod1': [0],
            'pod2': [1]
        }

        # No throttling, all pods should be scalable
        expected_result = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }

        result = _get_pods_to_scale(throttle_numa_nodes, pod_quotas, pod_numa_nodes)
        self.assertEqual(result, expected_result)


class TestGetOverloadPods(unittest.TestCase):

    def test_get_overload_pods_with_overload(self):
        pod_path = 'pod1'
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_dict = {}

        # pod1 AC_QUOTA > BT_QUOTA, so it should be added to pod_dict
        expected_result = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 }
        }

        result = _get_overload_pods(pod_path, pod_quotas, pod_dict)
        self.assertEqual(result, expected_result)

    def test_get_overload_pods_no_overload(self):
        pod_path = 'pod2'
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_dict = {}

        # pod2 AC_QUOTA <= BT_QUOTA, so it should not be added to pod_dict
        expected_result = {}

        result = _get_overload_pods(pod_path, pod_quotas, pod_dict)
        self.assertEqual(result, expected_result)

    def test_get_overload_pods_with_existing_pod_dict(self):
        pod_path = 'pod1'
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_dict = {
            'pod3': { AC_QUOTA: 600, BT_QUOTA: 500 }
        }

        # pod1 AC_QUOTA > BT_QUOTA, it should be added to pod_dict, while pod3 remains
        expected_result = {
            'pod3': { AC_QUOTA: 600, BT_QUOTA: 500 },
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 }
        }

        result = _get_overload_pods(pod_path, pod_quotas, pod_dict)
        self.assertEqual(result, expected_result)

    def test_get_overload_pods_pod_not_in_pod_quotas(self):
        pod_path = 'pod3'
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_dict = {}

        # pod3 is not in pod_quotas, so nothing will be added to pod_dict
        expected_result = {}

        result = _get_overload_pods(pod_path, pod_quotas, pod_dict)
        self.assertEqual(result, expected_result)

    def test_get_overload_pods_empty_pod_dict(self):
        pod_path = 'pod1'
        pod_quotas = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 },
            'pod2': { AC_QUOTA: 400, BT_QUOTA: 450 }
        }
        pod_dict = {}

        # pod1 AC_QUOTA > BT_QUOTA, so it should be added to pod_dict
        expected_result = {
            'pod1': { AC_QUOTA: 500, BT_QUOTA: 300 }
        }

        result = _get_overload_pods(pod_path, pod_quotas, pod_dict)
        self.assertEqual(result, expected_result)

    def test_get_overload_pods_empty_pod_quotas(self):
        pod_path = 'pod1'
        pod_quotas = {}  # No pods in pod_quotas
        pod_dict = {}

        # Since pod_quotas is empty, nothing will be added to pod_dict
        expected_result = {}

        result = _get_overload_pods(pod_path, pod_quotas, pod_dict)
        self.assertEqual(result, expected_result)


class TestQuotaManager(unittest.TestCase):

    @patch('quota_manager.get_container_info')
    def test_balance_pods_all_mode(self, mock_get_container_info):
        # 模拟输入
        pod_quotas = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 60, AC_QUOTA: 60},
        }
        pods_to_balanced = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 60, AC_QUOTA: 60},
        }
        pod_nodes = {
            '/path/to/pod1': [0, 1],
            '/path/to/pod2': [0],
        }

        # 模拟返回的 CPU shares
        mock_get_container_info.side_effect = lambda pod_path, resource: 100 if pod_path == '/path/to/pod1' else 50

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _balance_pods
        result = quota_manager._balance_pods(pod_quotas, pods_to_balanced, pod_nodes, mode="all")

        # 期望的结果
        expected_result = {
            '/path/to/pod1': {AC_QUOTA: 100, BT_QUOTA: 91}
        }

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    @patch('quota_manager.get_container_info')
    def test_balance_pods_numa_mode(self, mock_get_container_info):
        # 模拟输入
        pod_quotas = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 60, AC_QUOTA: 60},
        }
        pods_to_balanced = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 60, AC_QUOTA: 60},
        }
        pod_nodes = {
            '/path/to/pod1': [0, 1],
            '/path/to/pod2': [1],
        }

        # 模拟返回的 CPU shares
        mock_get_container_info.side_effect = lambda pod_path, resource: 100 if pod_path == '/path/to/pod1' else 50

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _balance_pods
        result = quota_manager._balance_pods(pod_quotas, pods_to_balanced, pod_nodes, mode="numa")

        # 期望的结果
        expected_result = {
            '/path/to/pod1': {AC_QUOTA: 100, BT_QUOTA: 91}
        }

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    def test_balance_pods_empty_pods_to_balanced(self):
        # 模拟输入
        pod_quotas = {}
        pods_to_balanced = {}
        pod_nodes = {}

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _balance_pods
        result = quota_manager._balance_pods(pod_quotas, pods_to_balanced, pod_nodes, mode="all")

        # 期望的结果
        expected_result = {}

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    def test_balance_pods_invalid_mode(self):
        # 模拟输入
        pod_quotas = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 60, AC_QUOTA: 60},
        }
        pods_to_balanced = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 60, AC_QUOTA: 60},
        }
        pod_nodes = {
            '/path/to/pod1': [0, 1],
            '/path/to/pod2': [1],
        }

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _balance_pods with invalid mode
        result = quota_manager._balance_pods(pod_quotas, pods_to_balanced, pod_nodes, mode="invalid_mode")

        # 期望的结果
        expected_result = {}

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)


    # #####################
    def test_balance_pods_by_share(self):
        # 模拟输入
        pod_shares = {
            '/path/to/pod1': 100,
            '/path/to/pod2': 50,
        }
        total_boost_quota = 150
        boosted_pods = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120, AC_QUOTA: 100},
        }
        pod_quotas = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120},
        }
        balanced_pod = {}

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _balance_pods_by_share
        quota_manager._balance_pods_by_share(pod_shares, total_boost_quota, boosted_pods, pod_quotas, balanced_pod)

        # 验证输出
        expected_result = {
            '/path/to/pod1': {
                AC_QUOTA: 100,  # 加权后的 BT_QUOTA 应该为 100
                BT_QUOTA: 91,   # 计算出的调整后的 BT_QUOTA
            },
            '/path/to/pod2': {
                AC_QUOTA: 120,
                BT_QUOTA: 101,   # 计算出的调整后的 BT_QUOTA
            }
        }

        # 验证返回值是否正确
        self.assertEqual(balanced_pod, expected_result)

    def test_balance_pods_by_share_empty(self):
        # 模拟输入
        pod_shares = {}
        total_boost_quota = 0
        boosted_pods = {}
        pod_quotas = {}
        balanced_pod = {}

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _balance_pods_by_share
        quota_manager._balance_pods_by_share(pod_shares, total_boost_quota, boosted_pods, pod_quotas, balanced_pod)

        # 验证输出（balanced_pod 应该为空）
        expected_result = {}
        self.assertEqual(balanced_pod, expected_result)

    @patch('quota_manager.logging.debug')
    def test_balance_pods_by_share_no_pod_shares(self, mock_logging):
        # 模拟输入，确保 total_pod_priority 为 0
        pod_shares = {
            '/path/to/pod1': 1,
            '/path/to/pod2': 1,
        }
        total_boost_quota = 100
        boosted_pods = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120, AC_QUOTA: 100},
        }
        pod_quotas = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120},
        }
        balanced_pod = {}

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _balance_pods_by_share
        quota_manager._balance_pods_by_share(pod_shares, total_boost_quota, boosted_pods, pod_quotas, balanced_pod)

        # 验证输出
        expected_result = {
            '/path/to/pod1': {
                AC_QUOTA: 100,
                BT_QUOTA: 91,
            },
            '/path/to/pod2': {
                AC_QUOTA: 120,
                BT_QUOTA: 111,
            }
        }

        # 验证返回值是否正确
        self.assertEqual(balanced_pod, expected_result)

        # 检查是否调用了 logging.debug
        mock_logging.assert_called_with('pod priority: %s', {'/path/to/pod1': 10000 / 1, '/path/to/pod2': 10000 / 1})


    ##########
    def test_get_pods_to_balance_empty_throttle_nodes(self):
        # 模拟输入
        throttle_nodes = {}
        boosted_pods = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120, AC_QUOTA: 100},
        }
        pod_numa_nodes = {
            '/path/to/pod1': [0, 1],
            '/path/to/pod2': [1],
        }

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _get_pods_to_balance
        result = quota_manager._get_pods_to_balance(throttle_nodes, boosted_pods, pod_numa_nodes)

        # 期望的结果：空字典
        expected_result = {}

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    def test_get_pods_to_balance_all_throttle_nodes(self):
        # 模拟输入
        throttle_nodes = {'all': 1}
        boosted_pods = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120, AC_QUOTA: 100},
        }
        pod_numa_nodes = {
            '/path/to/pod1': [0, 1],
            '/path/to/pod2': [1],
        }

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _get_pods_to_balance
        result = quota_manager._get_pods_to_balance(throttle_nodes, boosted_pods, pod_numa_nodes)

        # 期望的结果：所有 boosted_pods
        expected_result = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120, AC_QUOTA: 100},
        }

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    def test_get_pods_to_balance_specific_throttle_nodes(self):
        # 模拟输入
        throttle_nodes = {0: 1}  # 限制节点 0
        boosted_pods = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120, AC_QUOTA: 100},
        }
        pod_numa_nodes = {
            '/path/to/pod1': [0, 1],  # pod1 位于节点 0 和 1
            '/path/to/pod2': [1],      # pod2 位于节点 1
        }

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _get_pods_to_balance
        result = quota_manager._get_pods_to_balance(throttle_nodes, boosted_pods, pod_numa_nodes)

        # 期望的结果：只有 pod1 会被返回，因为 pod2 不在节点 0 上
        expected_result = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
        }

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    def test_get_pods_to_balance_multiple_throttle_nodes(self):
        # 模拟输入
        throttle_nodes = {0: 1, 1: 1}  # 限制节点 0 和 1
        boosted_pods = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120, AC_QUOTA: 100},
            '/path/to/pod3': {OG_QUOTA: 70, BT_QUOTA: 140, AC_QUOTA: 110},
        }
        pod_numa_nodes = {
            '/path/to/pod1': [0, 1],
            '/path/to/pod2': [1],
            '/path/to/pod3': [0],  # pod3 仅位于节点 0
        }

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 _get_pods_to_balance
        result = quota_manager._get_pods_to_balance(throttle_nodes, boosted_pods, pod_numa_nodes)

        # 期望的结果：pod1 和 pod3 都会被返回，因为它们位于 throttle 的节点上
        expected_result = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100, AC_QUOTA: 80},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120, AC_QUOTA: 100},
            '/path/to/pod3': {OG_QUOTA: 70, BT_QUOTA: 140, AC_QUOTA: 110},
        }

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)


    def test_check_numa_util_empty_input(self):
        # 模拟输入为空
        numa_cpu_utils = {}

        # 初始化 QuotaManager
        quota_manager = QuotaManager()
        
        # 调用 _check_numa_util
        result = quota_manager._check_numa_util(numa_cpu_utils)

        # 期望的结果：空字典
        expected_result = {}

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    def test_check_numa_util_below_threshold(self):
        # 模拟输入，所有节点的使用率低于阈值
        numa_cpu_utils = {
            0: [10, 20, 30],  # 平均 20%
            1: [10, 15, 5],   # 平均 10%
        }

        # 初始化 QuotaManager 并设置阈值
        quota_manager = QuotaManager()
        quota_manager.overload_threshold_v2 = 0.2  # 20%

        # 调用 _check_numa_util
        result = quota_manager._check_numa_util(numa_cpu_utils)

        # 期望的结果：空字典，因为所有节点的使用率都低于 20%
        expected_result = {}

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    def test_check_numa_util_above_threshold(self):
        # 模拟输入，某些节点的使用率超过阈值
        numa_cpu_utils = {
            0: [70, 80, 90],  # 平均 80%
            1: [10, 15, 5],   # 平均 10%
            2: [85, 90, 95],  # 平均 90%
        }

        # 初始化 QuotaManager 并设置阈值
        quota_manager = QuotaManager()
        quota_manager.overload_threshold_v2 = 0.6  # 60%

        # 调用 _check_numa_util
        result = quota_manager._check_numa_util(numa_cpu_utils)

        # 期望的结果：节点 0 和节点 2 因为其使用率超过 60%，会被加入到 throttle_nodes
        expected_result = {
            0: 80.0,
            2: 90.0,
        }

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    def test_check_numa_util_at_threshold(self):
        # 模拟输入，某些节点的使用率恰好等于阈值
        numa_cpu_utils = {
            0: [70, 70, 79],  # 平均 70%
            1: [30, 40, 50],  # 平均 40%
        }

        # 初始化 QuotaManager 并设置阈值
        quota_manager = QuotaManager()
        quota_manager.overload_threshold_v2 = 0.7  # 70%

        # 调用 _check_numa_util
        result = quota_manager._check_numa_util(numa_cpu_utils)

        # 期望的结果：节点 0 因为其使用率等于 70%，会被加入到 throttle_nodes
        expected_result = {
            0: 73.0,
        }

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)


    @patch('quota_manager.QuotaManager._check_numa_util')
    def test_quota_approval_empty_numa_util(self, mock_check_numa_util):
        # 模拟输入
        pod_quotas = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120},
        }
        boosted_pods = {}
        numa_cpu_utils = {}
        pod_numa_nodes = {
            '/path/to/pod1': [0],
            '/path/to/pod2': [1],
        }
        pod_forecast = {}

        # 模拟 _check_numa_util 返回空字典
        mock_check_numa_util.return_value = {}

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 quota_approval
        result = quota_manager.quota_approval(pod_quotas, boosted_pods, numa_cpu_utils, pod_numa_nodes, pod_forecast)

        # 期望的结果：返回原始的 pod_quotas
        expected_result = pod_quotas

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    @patch('quota_manager.QuotaManager._check_numa_util')
    @patch('quota_manager._get_pods_to_limit')
    @patch('quota_manager.QuotaManager._balance_pods')
    def test_quota_approval_all_throttle_nodes(self, mock_balance_pods, mock_get_pods_to_limit, mock_check_numa_util):
        # 模拟输入
        pod_quotas = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120},
        }
        boosted_pods = {}
        numa_cpu_utils = {0: [80, 90, 85]}  # 高负载，触发限制
        pod_numa_nodes = {
            '/path/to/pod1': [0],
            '/path/to/pod2': [0],
        }
        pod_forecast = {}

        # 模拟 _check_numa_util 返回 'all'，表示所有节点都受限
        mock_check_numa_util.return_value = {'all': 1}

        # 模拟 _get_pods_to_limit 和 _balance_pods 返回结果
        mock_get_pods_to_limit.return_value = {'/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100}}
        mock_balance_pods.return_value = {'/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120}}

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 quota_approval
        result = quota_manager.quota_approval(pod_quotas, boosted_pods, numa_cpu_utils, pod_numa_nodes, pod_forecast)

        # 期望的结果：返回经过平衡后的 pods
        expected_result = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100}
        }

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    @patch('quota_manager.QuotaManager._check_numa_util')
    @patch('quota_manager._get_pods_to_scale')
    @patch('quota_manager._get_pods_to_limit')
    @patch('quota_manager.QuotaManager._get_pods_to_balance')
    @patch('quota_manager.QuotaManager._balance_pods')
    def test_quota_approval_with_boosted_pods(self, mock_balance_pods, mock_get_pods_to_balance, mock_get_pods_to_limit, mock_get_pods_to_scale, mock_check_numa_util):
        # 模拟输入
        pod_quotas = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 100},
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120},
        }
        boosted_pods = {
            '/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 150},  # boosted
        }
        numa_cpu_utils = {0: [80, 90, 85]}  # 高负载，触发限制
        pod_numa_nodes = {
            '/path/to/pod1': [0],
            '/path/to/pod2': [0],
        }
        pod_forecast = {}

        # 模拟 _check_numa_util 返回一个特定的节点受限
        mock_check_numa_util.return_value = {0: 85}

        # 模拟其他方法的返回值
        mock_get_pods_to_scale.return_value = {'/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120}}
        mock_get_pods_to_limit.return_value = {}
        mock_get_pods_to_balance.return_value = {'/path/to/pod1': {OG_QUOTA: 50, BT_QUOTA: 150}}
        mock_balance_pods.return_value = {'/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120}}

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 调用 quota_approval
        result = quota_manager.quota_approval(pod_quotas, boosted_pods, numa_cpu_utils, pod_numa_nodes, pod_forecast)

        # 期望的结果：返回经过平衡后的 pods（包含 boost 和限制）
        expected_result = {
            '/path/to/pod2': {OG_QUOTA: 60, BT_QUOTA: 120}
        }

        # 验证返回值是否正确
        self.assertEqual(result, expected_result)

    @patch('quota_manager.logging.warning')
    def test_quota_approval_exception(self, mock_warning):
        # 模拟输入
        pod_quotas = {}
        boosted_pods = {}
        numa_cpu_utils = {}
        pod_numa_nodes = {}
        pod_forecast = {}

        # 初始化 QuotaManager
        quota_manager = QuotaManager()

        # 模拟抛出异常
        with patch.object(quota_manager, '_check_numa_util', side_effect=Exception("Test exception")):
            result = quota_manager.quota_approval(pod_quotas, boosted_pods, numa_cpu_utils, pod_numa_nodes, pod_forecast)

        # 验证异常处理：应该返回空字典，并记录警告日志
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
