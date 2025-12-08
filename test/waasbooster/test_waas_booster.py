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

import unittest
from unittest import mock
from unittest.mock import patch, mock_open, MagicMock
import os
import json
import sys
import time
import threading
from datetime import datetime, timezone, timedelta
from collections import deque, defaultdict

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
import util
from util import get_boosted_container_cgroups, get_container_info, AC_QUOTA, AVG_QUOTA_UTIL, CGROUP_QUOTA, \
                 EXPAND_MODE, SCALING_MODE, BT_QUOTA
from waas_booster import QuotaBooster
from quota_calculator import PIDController

logging.set_log_instance("INFO")


class TestQuotaBooster(unittest.TestCase):
    
    def setUp(self):
        """初始化一个QuotaBooster实例用于测试"""
        self.qb = QuotaBooster(
            monitor_interval=0.1,
            queue_max_len=15,
            refresh_interval=60,
            over_load_threshold=0.9,
            down_load_threshold=0.3,
            expand_cor=1.2,
            scaling_cor=0.9,
            boost_interval=10,
            unboost_interval=30,
            max_expand_limit=3.0,
            min_scaling_limit=1.0,
            data_collect=False,
            data_collector_interval=600,
            data_monitor_interval=1,
            numa_balance_interval=10,
            forecast=True
        )

    def tearDown(self):
        self.qb.stop()

    def test_valid_params(self):
        """测试当所有参数都有效时，check_init_param不会抛出异常"""
        try:
            self.qb.check_init_param()  # 假设有效的输入不会抛出异常
        except ValueError as e:
            self.fail(f"check_init_param raised ValueError unexpectedly: {str(e)}")

    def test_over_load_threshold_invalid(self):
        """测试 over_load_threshold 参数无效"""
        self.qb.over_load_threshold = 1.5
        with self.assertRaises(ValueError) as context:
            self.qb.check_init_param()
        self.assertTrue('over_load_threshold must be between 0 and 1' in str(context.exception))

    def test_down_load_threshold_invalid(self):
        """测试 down_load_threshold 参数无效"""
        self.qb.down_load_threshold = -0.1
        with self.assertRaises(ValueError) as context:
            self.qb.check_init_param()
        self.assertTrue('down_load_threshold must be between 0 and 1' in str(context.exception))

    def test_expand_cor_invalid(self):
        """测试 expand_cor 参数无效"""
        self.qb.expand_cor = 1.0
        with self.assertRaises(ValueError) as context:
            self.qb.check_init_param()
        self.assertTrue('expand_cor must be greater than 1' in str(context.exception))

    def test_scaling_cor_invalid(self):
        """测试 scaling_cor 参数无效"""
        self.qb.scaling_cor = 1.5
        with self.assertRaises(ValueError) as context:
            self.qb.check_init_param()
        self.assertTrue('scaling_cor must be between 0 and 1' in str(context.exception))

    def test_max_expand_limit_invalid(self):
        """测试 max_expand_limit 参数无效"""
        self.qb.max_expand_limit = 0.5
        with self.assertRaises(ValueError) as context:
            self.qb.check_init_param()
        self.assertTrue('max_expand_limit must be greater than 1' in str(context.exception))

    def test_min_scaling_limit_invalid(self):
        """测试 min_scaling_limit 参数无效"""
        self.qb.min_scaling_limit = 1.5
        with self.assertRaises(ValueError) as context:
            self.qb.check_init_param()
        self.assertTrue('min_scaling_limit must be between 0 and 1' in str(context.exception))

    def test_boost_interval_invalid(self):
        """测试 boost_interval 参数无效"""
        self.qb.boost_interval = self.qb.queue_max_len * self.qb.monitor_interval - 0.01
        with self.assertRaises(ValueError) as context:
            self.qb.check_init_param()
        self.assertTrue('boost_interval must be greater than monitor_interval *' in str(context.exception))

    def test_unboost_interval_invalid(self):
        """测试 unboost_interval 参数无效"""
        self.qb.unboost_interval = self.qb.queue_max_len * self.qb.monitor_interval - 0.01
        with self.assertRaises(ValueError) as context:
            self.qb.check_init_param()
        self.assertTrue('unboost_interval must be greater than monitor_interval *' in str(context.exception))

    def test_queue_max_len_invalid(self):
        """测试 queue_max_len 参数无效"""
        self.qb.queue_max_len = 5
        with self.assertRaises(ValueError) as context:
            self.qb.check_init_param()
        self.assertTrue('queue_max_len must be greater than 10' in str(context.exception))


class TestQuotaBoosterQuotaSet(unittest.TestCase):

    @patch('waas_booster.quota_updater')
    def test_quota_set_empty_input(self, mock_quota_updater):
        result = QuotaBooster.quota_set({})
        mock_quota_updater.assert_not_called()
        self.assertIsNone(result)

    @patch('waas_booster.quota_updater')
    def test_quota_set_bt_equal_ac(self, mock_quota_updater):
        pod_dict = {
            "/sys/fs/cgroup/pod1": {BT_QUOTA: 1000, AC_QUOTA: 1000}
        }
        result = QuotaBooster.quota_set(pod_dict)
        mock_quota_updater.assert_not_called()
        self.assertIsNone(result)

    @patch('waas_booster.quota_updater')
    def test_quota_set_bt_not_equal_ac(self, mock_quota_updater):
        pod_dict = {
            "/sys/fs/cgroup/pod1": {BT_QUOTA: 2000, AC_QUOTA: 1000}
        }
        mock_quota_updater.return_value = "quota_updated"
        result = QuotaBooster.quota_set(pod_dict)
        mock_quota_updater.assert_called_once_with("/sys/fs/cgroup/pod1", 2000)
        self.assertEqual(result, "quota_updated")

    @patch('waas_booster.quota_updater')
    def test_quota_set_multiple_pods(self, mock_quota_updater):
        pod_dict = {
            "/sys/fs/cgroup/pod1": {BT_QUOTA: 1000, AC_QUOTA: 1000},  # 不触发
            "/sys/fs/cgroup/pod2": {BT_QUOTA: 2000, AC_QUOTA: 1500},  # 触发
            "/sys/fs/cgroup/pod3": {BT_QUOTA: 3000, AC_QUOTA: 1000},  # 触发
        }
        mock_quota_updater.side_effect = ["resp2", "resp3"]
        result = QuotaBooster.quota_set(pod_dict)
        self.assertEqual(mock_quota_updater.call_count, 2)
        self.assertEqual(result, "resp3")


class TestQuotaBoosterCpuUtilQueueStart(unittest.TestCase):

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")  # Mock NUMA 和 load_collect 的线程
    @patch("waas_booster.CpuMonitor")
    def test_cpu_util_queue_start_success(
        self, mock_cpu_monitor_cls, mock_thread_cls,
        mock_numa_cls, mock_get_pod_og_quota, mock_get_all_pod):
        # 模拟 CpuMonitor 和 Thread
        mock_cpu_monitor = MagicMock()
        mock_thread = MagicMock()
        mock_cpu_monitor_cls.return_value = mock_cpu_monitor
        mock_thread_cls.return_value = mock_thread

        # 创建实例
        booster = QuotaBooster()
        booster.pod_path = "/some/pod/path"
        booster.monitor_interval = 0.2

        # 调用被测方法
        result = booster.cpu_util_queue_start()

        # 验证 CpuMonitor 初始化和线程启动
        mock_cpu_monitor_cls.assert_called_once_with(booster.over_load_threshold, booster.queue_max_len)
        mock_thread_cls.assert_any_call(target=mock_cpu_monitor.run, args=("/some/pod/path", 0.2))
        mock_thread.start.assert_called()  # 至少被调用一次
        self.assertEqual(result, mock_cpu_monitor)

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    @patch("waas_booster.CpuMonitor")
    @patch("waas_booster.logging.error")
    def test_cpu_util_queue_start_failure(
        self, mock_log_error, mock_cpu_monitor_cls, mock_thread_cls,
        mock_numa_cls, mock_get_pod_og_quota, mock_get_all_pod):
        # 模拟异常（线程创建失败）
        mock_cpu_monitor = MagicMock()
        mock_cpu_monitor_cls.return_value = mock_cpu_monitor
        mock_thread_cls.side_effect = Exception("Thread error")
        with self.assertRaises(Exception) as context:
            booster = QuotaBooster()
        mock_log_error.assert_called()


class TestQuotaBoosterInitQuotaRecord(unittest.TestCase):

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    @patch("os.open")
    def test_init_quota_record_success(self, mock_file, mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()
        quota_dict = {"pod1": {"cpu": 2}}

        result = booster.init_quota_record(quota_dict)

        mock_file.assert_called_once_with(booster.init_quota_file, os.O_WRONLY | os.O_CREAT, 0o600)
        self.assertFalse(result)

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    @patch("waas_booster.logging.warning")
    @patch("os.open")
    def test_init_quota_record_failure(self, mock_file, mock_log_warning,
                                       mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()
        quota_dict = {"pod1": {"cpu": 2}}

        result = booster.init_quota_record(quota_dict)

        mock_file.assert_called_once_with(booster.init_quota_file, os.O_WRONLY | os.O_CREAT, 0o600)
        mock_log_warning.assert_called_once()
        self.assertFalse(result)


class TestQuotaBoosterInitQuotaLoad(unittest.TestCase):

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    @patch("os.path.exists", return_value=False)
    def test_init_quota_load_file_not_exist(self, mock_exists, mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()
        result = booster.init_quota_load()

        mock_exists.assert_called_with(booster.init_quota_file)
        self.assertEqual(result, {})

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='{"pod1": {"cpu": 2}}')
    def test_init_quota_load_success(self, mock_file, mock_exists, mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()
        result = booster.init_quota_load()

        self.assertEqual(result, {"pod1": {"cpu": 2}})
        mock_file.assert_called_once_with(booster.init_quota_file, 'r', encoding='utf-8')

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    @patch("os.path.exists", return_value=True)
    @patch("waas_booster.logging.warning")
    @patch("builtins.open", new_callable=mock_open, read_data='{bad json}')
    def test_init_quota_load_json_error(self, mock_file, mock_log_warning, mock_exists,
                                        mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()

        with patch("json.load", side_effect=ValueError("Invalid JSON")):
            result = booster.init_quota_load()

        self.assertEqual(result, {})
        mock_log_warning.assert_called_once()


class TestQuotaBoosterCleanup(unittest.TestCase):

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    def test_cleanup_all_exist(self, mock_remove, mock_exists, mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()
        booster.cleanup()

        self.assertEqual(mock_remove.call_count, 2)
        mock_remove.assert_any_call(booster.pid_file)
        mock_remove.assert_any_call(booster.init_quota_file)

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    @patch("os.path.exists", return_value=False)
    @patch("os.remove")
    @patch("waas_booster.logging.warning")
    def test_cleanup_raises_exception(self, mock_log, mock_remove, mock_exists,
                                      mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()
        booster.cleanup()

        mock_remove.assert_not_called()


class TestQuotaBoosterCheckPodStatus(unittest.TestCase):

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    def test_check_pod_status_updates(self, mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()

        cpu_queue_dict = {
            "/cgroup/container1": {AC_QUOTA: 100},
            "/cgroup/container2": {AC_QUOTA: 200},
        }

        with patch.object(booster, 'calculate_container_quota', side_effect=[150, None]):
            result = booster.check_pod_status(cpu_queue_dict, {})

        expected = {
            "/cgroup/container1": {
                BT_QUOTA: 150,
                AC_QUOTA: 100
            }
        }

        self.assertEqual(result, expected)

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    def test_check_pod_status_empty_input(self, mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()

        cpu_queue_dict = {}
        result = booster.check_pod_status(cpu_queue_dict, {})
        self.assertEqual(result, {})

    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=("/pod/path", ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={})
    @patch("waas_booster.NUMAMonitor")
    @patch("waas_booster.threading.Thread")
    def test_check_pod_status_merge_into_existing_dict(self, mock_thread, mock_numa, mock_get_quota, mock_get_pod):
        booster = QuotaBooster()

        cpu_queue_dict = {
            "/cgroup/containerX": {AC_QUOTA: 90}
        }
        existing_dict = {
            "/existing/container": {BT_QUOTA: 123, AC_QUOTA: 456}
        }

        with patch.object(booster, 'calculate_container_quota', return_value=75):
            result = booster.check_pod_status(cpu_queue_dict, existing_dict.copy())

        self.assertIn("/cgroup/containerX", result)
        self.assertIn("/existing/container", result)
        self.assertEqual(result["/cgroup/containerX"][BT_QUOTA], 75)
        self.assertEqual(result["/cgroup/containerX"][AC_QUOTA], 90)


class TestQuotaBoosterRefreshPodPath(unittest.TestCase):

    @patch("waas_booster.get_container_info", return_value="80000")
    @patch("waas_booster.QuotaBooster.init_quota_record", return_value=True)
    @patch("waas_booster.QuotaBooster.cpu_util_queue_start")
    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp/mock_booster")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=(["/mock/newpod"], ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={"/mock/oldpod": 50000})
    @patch("waas_booster.QuotaBooster.check_init_param")
    @patch("waas_booster.NUMAMonitor")
    def test_refresh_pod_path_with_new_pod(
        self,
        mock_numa,
        mock_check_param,
        mock_get_quota,
        mock_get_all_pod,
        mock_queue_start,
        mock_init_quota,
        mock_get_container_info
    ):
        # Setup booster with existing pod path
        booster = QuotaBooster(forecast=False)
        booster.pod_path = ["/mock/oldpod"]
        booster.cpu_monitor = MagicMock()
        booster.cpu_monitor_thread = MagicMock()
        booster.cpu_monitor_thread.is_alive.side_effect = [True, False]  # Simulate join loop ending

        returned_path = booster.refresh_pod_path()

        self.assertEqual(returned_path, ["/mock/newpod"])
        self.assertIn("/mock/newpod", booster.pod_og_quota)
        self.assertTrue(mock_get_container_info.called)
        self.assertTrue(mock_queue_start.called)
        self.assertTrue(mock_init_quota.called)
        booster.cpu_monitor.stop.assert_called_once()
        booster.cpu_monitor_thread.join.assert_called_once()

    @patch("waas_booster.QuotaBooster.cpu_util_queue_start")
    @patch("waas_booster.util.WAAS_BOOSTER_MANAGER", "/tmp/mock_booster")
    @patch("waas_booster.QuotaBooster.get_all_pod", return_value=(["/mock/oldpod"], ["node0"]))
    @patch("waas_booster.QuotaBooster.get_pod_og_quota", return_value={"/mock/oldpod": 50000})
    @patch("waas_booster.QuotaBooster.check_init_param")
    @patch("waas_booster.NUMAMonitor")
    def test_refresh_pod_path_no_change(
        self,
        mock_numa,
        mock_check_param,
        mock_get_quota,
        mock_get_all_pod,
        mock_queue_start
    ):
        booster = QuotaBooster(forecast=False)
        booster.pod_path = ["/mock/oldpod"]

        returned_path = booster.refresh_pod_path()

        self.assertEqual(returned_path, ["/mock/oldpod"])
        mock_queue_start.assert_not_called()  # No change → no restart


class TestQuotaBoosterCpuUtilQueueStart(unittest.TestCase):

    @patch('waas_booster.CpuMonitor')
    @patch('waas_booster.QuotaBooster.check_init_param')
    @patch('waas_booster.QuotaBooster.get_all_pod', return_value=([], []))
    @patch('waas_booster.QuotaBooster.get_pod_og_quota', return_value={})
    @patch('waas_booster.NUMAMonitor')
    def test_cpu_util_queue_start_success(
        self, mock_numa, mock_get_quota, mock_get_all_pod, mock_check_param, mock_cpu_monitor
    ):
        # Arrange
        booster = QuotaBooster(forecast=False)
        booster.pod_path = ['/mock/pod']
        mock_monitor_instance = MagicMock()
        mock_cpu_monitor.return_value = mock_monitor_instance

        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            # Act
            result = booster.cpu_util_queue_start()

            # Assert
            mock_cpu_monitor.assert_called_once_with(booster.over_load_threshold, booster.queue_max_len)
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()
            self.assertEqual(result, mock_monitor_instance)

    @patch('waas_booster.CpuMonitor', side_effect=RuntimeError("Mocked failure"))
    @patch('waas_booster.QuotaBooster.check_init_param')
    @patch('waas_booster.QuotaBooster.get_all_pod', return_value=([], []))
    @patch('waas_booster.QuotaBooster.get_pod_og_quota', return_value={})
    @patch('waas_booster.NUMAMonitor')
    def test_cpu_util_queue_start_failure(
        self, mock_numa, mock_get_quota, mock_get_all_pod, mock_check_param, mock_cpu_monitor
    ):
        # Arrange
        booster = QuotaBooster(forecast=False)
        booster.pod_path = ['/mock/pod']

        # Act & Assert
        with self.assertRaises(Exception) as context:
            booster.cpu_util_queue_start()

        self.assertIn("cpu monitor start failed", str(context.exception))


class TestQuotaBoosterUpdateContainerQueueTime(unittest.TestCase):

    @patch('waas_booster.QuotaBooster.check_init_param')
    @patch('waas_booster.QuotaBooster.get_all_pod', return_value=([], []))
    @patch('waas_booster.QuotaBooster.get_pod_og_quota', return_value={})
    @patch('waas_booster.NUMAMonitor')
    def setUp(self, mock_numa, mock_quota, mock_get_all_pod, mock_check_param):
        self.booster = QuotaBooster(forecast=False)

    @patch('time.time', return_value=100.0)
    def test_new_path_should_return_true(self, mock_time):
        result = self.booster.update_container_queue_time("/test/container1", 10)
        self.assertTrue(result)
        self.assertIn("/test/container1", self.booster.container_update_queue)
        self.assertEqual(self.booster.container_update_queue["/test/container1"], 100.0)

    @patch('time.time', side_effect=[200.0, 215.0])
    def test_existing_path_and_interval_exceeded_should_return_true(self, mock_time):
        self.booster.container_update_queue["/test/container2"] = 200.0
        result = self.booster.update_container_queue_time("/test/container2", 10)
        self.assertFalse(result)
        self.assertEqual(self.booster.container_update_queue["/test/container2"], 200.0)

    @patch('time.time', side_effect=[300.0, 305.0])
    def test_existing_path_and_interval_not_exceeded_should_return_false(self, mock_time):
        self.booster.container_update_queue["/test/container3"] = 300.0
        result = self.booster.update_container_queue_time("/test/container3", 10)
        self.assertFalse(result)
        self.assertEqual(self.booster.container_update_queue["/test/container3"], 300.0)  # unchanged


class TestQuotaBoosterCalculateContainerQuota(unittest.TestCase):

    @patch('waas_booster.QuotaBooster.check_init_param')
    @patch('waas_booster.QuotaBooster.get_all_pod', return_value=([], []))
    @patch('waas_booster.QuotaBooster.get_pod_og_quota', return_value={})
    @patch('waas_booster.NUMAMonitor')
    def setUp(self, mock_numa, mock_quota, mock_pod, mock_check):
        self.booster = QuotaBooster(forecast=False)
        self.booster.quota_calculate = MagicMock(return_value=1500)

    @patch.object(QuotaBooster, 'update_container_queue_time', return_value=True)
    def test_expand_condition_met(self, mock_update):
        container_info = {AVG_QUOTA_UTIL: self.booster.over_load_threshold * 100 + 5}
        result = self.booster.calculate_container_quota('/c1', container_info)
        self.booster.quota_calculate.assert_called_with('/c1', EXPAND_MODE, container_info)
        self.assertEqual(result, 1500)

    @patch.object(QuotaBooster, 'update_container_queue_time', return_value=True)
    def test_scale_condition_met(self, mock_update):
        container_info = {AVG_QUOTA_UTIL: self.booster.down_load_threshold * 100 - 5}
        result = self.booster.calculate_container_quota('/c2', container_info)
        self.booster.quota_calculate.assert_called_with('/c2', SCALING_MODE, container_info)
        self.assertEqual(result, 1500)

    @patch.object(QuotaBooster, 'update_container_queue_time', return_value=False)
    def test_update_queue_time_returns_false(self, mock_update):
        container_info = {AVG_QUOTA_UTIL: self.booster.over_load_threshold * 100 + 10}
        result = self.booster.calculate_container_quota('/c3', container_info)
        self.assertIsNone(result)
        self.booster.quota_calculate.assert_not_called()

    def test_no_avg_util_key(self):
        container_info = {}
        result = self.booster.calculate_container_quota('/c4', container_info)
        self.assertIsNone(result)

    @patch.object(QuotaBooster, 'update_container_queue_time', side_effect=Exception("test error"))
    def test_exception_handling(self, mock_update):
        container_info = {AVG_QUOTA_UTIL: self.booster.over_load_threshold * 100 + 10}
        with self.assertRaises(Exception) as context:
            self.booster.calculate_container_quota('/c5', container_info)
        self.assertIn("update container quota error for", str(context.exception))


class TestQuotaBoosterQuotaCalculate(unittest.TestCase):

    @patch('waas_booster.QuotaBooster.check_init_param')
    @patch('waas_booster.QuotaBooster.get_all_pod', return_value=([], []))
    @patch('waas_booster.QuotaBooster.get_pod_og_quota', return_value={})
    @patch('waas_booster.NUMAMonitor')
    def setUp(self, mock_numa, mock_quota, mock_pods, mock_check):
        self.booster = QuotaBooster(forecast=False)
        self.container_path = '/test/path'
        self.ac_quota = 1000
        self.booster.pod_og_quota[self.container_path] = 1000

    def test_cor_mode_expand_within_limit(self):
        self.booster.quota_cal_mode = 'cor'
        self.booster.expand_cor = 1.5
        container_info = {AC_QUOTA: self.ac_quota}
        expected = 1500
        result = self.booster.quota_calculate(self.container_path, EXPAND_MODE, container_info)
        self.assertEqual(result, expected)

    def test_cor_mode_expand_exceeds_max_limit(self):
        self.booster.quota_cal_mode = 'cor'
        self.booster.expand_cor = 4.0  # > max_expand_limit
        self.booster.max_expand_limit = 3.0
        container_info = {AC_QUOTA: self.ac_quota}
        expected = 1000 * 3.0
        result = self.booster.quota_calculate(self.container_path, EXPAND_MODE, container_info)
        self.assertEqual(result, expected)

    def test_cor_mode_scaling_above_min_limit(self):
        self.booster.quota_cal_mode = 'cor'
        self.booster.scaling_cor = 0.8
        self.booster.min_scaling_limit = 0.5
        container_info = {AC_QUOTA: self.ac_quota}
        expected = 800
        result = self.booster.quota_calculate(self.container_path, SCALING_MODE, container_info)
        self.assertEqual(result, expected)

    def test_cor_mode_scaling_below_min_limit(self):
        self.booster.quota_cal_mode = 'cor'
        self.booster.scaling_cor = 0.3  # < min_scaling_limit
        self.booster.min_scaling_limit = 0.5
        container_info = {AC_QUOTA: self.ac_quota}
        expected = 500
        result = self.booster.quota_calculate(self.container_path, SCALING_MODE, container_info)
        self.assertEqual(result, expected)

    @patch('waas_booster.QuotaBooster.init_pid')
    def test_pid_mode_expand(self, mock_init_pid):
        self.booster.quota_cal_mode = 'pid'
        mock_pid_obj = MagicMock()
        mock_pid_obj.update.return_value = 1800
        mock_init_pid.return_value = mock_pid_obj
        container_info = {AC_QUOTA: self.ac_quota}
        result = self.booster.quota_calculate(self.container_path, EXPAND_MODE, container_info)
        mock_pid_obj.update.assert_called_once()
        self.assertEqual(result, 1800)

    @patch('waas_booster.QuotaBooster.init_pid')
    def test_pid_mode_scaling(self, mock_init_pid):
        self.booster.quota_cal_mode = 'pid'
        mock_pid_obj = MagicMock()
        mock_pid_obj.update.return_value = 700
        mock_init_pid.return_value = mock_pid_obj
        container_info = {AC_QUOTA: self.ac_quota}
        result = self.booster.quota_calculate(self.container_path, SCALING_MODE, container_info)
        mock_pid_obj.update.assert_called_once()
        self.assertEqual(result, 700)


class TestQuotaBoosterRestoreInitQuota(unittest.TestCase):

    @patch('waas_booster.quota_updater')
    @patch('waas_booster.QuotaBooster.check_init_param')
    @patch('waas_booster.QuotaBooster.get_all_pod', return_value=([], []))
    @patch('waas_booster.QuotaBooster.get_pod_og_quota', return_value={})
    @patch('waas_booster.NUMAMonitor')
    def setUp(self, mock_numa, mock_get_quota, mock_get_pods, mock_check, mock_quota_updater):
        self.booster = QuotaBooster(forecast=False)

    @patch('waas_booster.quota_updater')
    def test_restore_quota_success(self, mock_quota_updater):
        self.booster.pod_path = ['/pod1', '/pod2']
        self.booster.pod_og_quota = {
            '/pod1': 1000,
            '/pod2': 2000
        }
        mock_quota_updater.return_value = True

        self.booster.restore_init_quota()

        mock_quota_updater.assert_any_call('/pod1', 1000)
        mock_quota_updater.assert_any_call('/pod2', 2000)
        self.assertEqual(mock_quota_updater.call_count, 2)

    @patch('waas_booster.quota_updater')
    def test_restore_quota_partial_failure(self, mock_quota_updater):
        self.booster.pod_path = ['/pod1', '/pod2']
        self.booster.pod_og_quota = {
            '/pod1': 1000,
            '/pod2': 2000
        }
        # 模拟一个成功，一个失败
        mock_quota_updater.side_effect = [True, False]

        self.booster.restore_init_quota()

        mock_quota_updater.assert_any_call('/pod1', 1000)
        mock_quota_updater.assert_any_call('/pod2', 2000)
        self.assertEqual(mock_quota_updater.call_count, 2)

    def test_restore_quota_no_pods(self):
        self.booster.pod_path = []
        # 不应该调用 quota_updater
        with patch('waas_booster.quota_updater') as mock_quota_updater:
            self.booster.restore_init_quota()
            mock_quota_updater.assert_not_called()


class TestQuotaBoosterGetPodOgQuota(unittest.TestCase):

    @patch('waas_booster.get_container_info')
    @patch('waas_booster.QuotaBooster.init_quota_record')
    @patch('waas_booster.QuotaBooster.init_quota_load')
    @patch('waas_booster.QuotaBooster.check_init_param')
    @patch('waas_booster.QuotaBooster.get_all_pod', return_value=([], []))
    @patch('waas_booster.QuotaBooster.get_pod_og_quota', return_value={})
    @patch('waas_booster.NUMAMonitor')
    def setUp(self, mock_numa, mock_get_quota, mock_get_pods, mock_check, mock_init_load, mock_init_record, mock_container_info):
        self.booster = QuotaBooster(forecast=False)

    @patch('waas_booster.get_container_info')
    @patch('waas_booster.QuotaBooster.init_quota_record')
    @patch('waas_booster.QuotaBooster.init_quota_load')
    def test_get_pod_og_quota_success(self, mock_load, mock_record, mock_get_info):
        self.booster.pod_path = ['/pod1', '/pod2']
        mock_load.return_value = {'/pod2': 5000}
        mock_get_info.side_effect = lambda path, key: {'/pod1': 1000, '/pod2': 2000}[path] if key == CGROUP_QUOTA else None

        result = self.booster.get_pod_og_quota()

        expected = {
            '/pod1': 1000,
            '/pod2': 5000  # 来自 init_quota_dict，会覆盖 container_info 的值
        }

        self.assertEqual(result, expected)
        mock_get_info.assert_any_call('/pod1', CGROUP_QUOTA)
        mock_get_info.assert_any_call('/pod2', CGROUP_QUOTA)
        mock_record.assert_called_once_with(expected)

    @patch('waas_booster.get_container_info')
    @patch('waas_booster.QuotaBooster.init_quota_record')
    @patch('waas_booster.QuotaBooster.init_quota_load')
    def test_get_pod_og_quota_all_from_container_info(self, mock_load, mock_record, mock_get_info):
        self.booster.pod_path = ['/pod3']
        mock_load.return_value = {}
        mock_get_info.return_value = 8000

        result = self.booster.get_pod_og_quota()

        self.assertEqual(result, {'/pod3': 8000})
        mock_get_info.assert_called_once_with('/pod3', CGROUP_QUOTA)
        mock_record.assert_called_once_with({'/pod3': 8000})


class TestQuotaBoosterLoadForecast(unittest.TestCase):

    @patch('waas_booster.datetime')
    def test_load_forecast_not_triggered_due_to_wrong_time(self, mock_datetime):
        qb = QuotaBooster()
        qb.forecast = True
        qb.last_forecast_time = datetime(2025, 8, 5, 0, 0, tzinfo=timezone.utc)

        # 模拟当前时间非 00:05（不满足触发条件）
        mock_now = datetime(2025, 8, 6, 12, 30, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        result = qb.load_forecast()
        self.assertIsNone(result)
        qb.stop()

    @patch('waas_booster.datetime')
    def test_load_forecast_skipped_if_already_done_today(self, mock_datetime):
        qb = QuotaBooster()
        qb.forecast = True

        # 模拟当前是 00:05
        current_time = datetime(2025, 8, 6, 0, 5, tzinfo=timezone.utc)
        mock_datetime.now.return_value = current_time

        # 设置 last_forecast_time 为今天（已执行）
        qb.last_forecast_time = datetime(2025, 8, 6, 0, 0, tzinfo=timezone.utc)

        result = qb.load_forecast()
        self.assertIsNone(result)
        qb.stop()

    @patch('waas_booster.get_forecast_load')
    @patch('waas_booster.copy.copy')
    @patch('waas_booster.datetime')
    def test_load_forecast_successfully_runs(self, mock_datetime, mock_copy, mock_forecast):
        qb = QuotaBooster()
        qb.forecast = True
        qb.lock = MagicMock()
        qb.pod_data = {'mock_pod': {'sum': 100, 'count': 10}}

        # 设置 last_forecast_time 为前一天
        qb.last_forecast_time = datetime(2025, 8, 5, 23, 59, tzinfo=timezone.utc)

        # 当前为 00:05
        mock_now = datetime(2025, 8, 5, 16, 5, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now

        # 模拟 pod_data 和预测返回值
        mock_copy_data = {'mock_pod': {'sum': 100, 'count': 10}}
        mock_copy.return_value = mock_copy_data
        mock_forecast.return_value = {'mock_pod': 75.0}

        result = qb.load_forecast()

        self.assertEqual(result, {'mock_pod': 75.0})
        mock_forecast.assert_called_once_with(mock_copy_data)
        qb.stop()


class TestQuotaBoosterLoadCollect(unittest.TestCase):
    @patch("time.sleep")  # 避免 sleep 阻塞
    def test_load_collect_all_conditions(self, mock_sleep):
        # 构造 booster 实例，关闭 forecast 防止线程自动启动
        booster = QuotaBooster(forecast=False)
        booster.monitor_interval = 0.01
        booster.queue_max_len = 1
        booster.load_collect_thread = MagicMock()


        # 模拟 running 为 True -> 仅运行一次
        booster.running = True

        # 模拟 pod 路径
        pod_path = "/fake/pod1"

        # 设置当前时间为 0 或 30 分钟，模拟触发 half_hour_avg 逻辑
        current_time = datetime(2025, 8, 5, 10, 0, tzinfo=timezone.utc) + timedelta(hours=8)

        # 模拟 cpu_queue_dict 有 pod 数据
        booster.cpu_queue_dict = {
            pod_path: {
                util.CPU_UTIL: [0.5, 0.7, 0.6]
            }
        }

        # 初始化 pod_data
        booster.pod_data[pod_path]['sum'] = 0
        booster.pod_data[pod_path]['count'] = 0
        booster.pod_data[pod_path]['start_time'] = current_time - timedelta(seconds=1800)
        booster.pod_data[pod_path]['qualified'] = True
        booster.pod_data[pod_path]['last_processed_minute'] = None

        # patch datetime.now 返回固定时间（模拟 current_time 为 10:00）
        with patch("waas_booster.datetime") as mock_datetime:
            mock_datetime.now.return_value = current_time
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            mock_datetime.timezone = timezone
            mock_datetime.timedelta = timedelta

            # 运行一次后终止
            def stop_after_once(*args, **kwargs):
                booster.running = False
            mock_sleep.side_effect = stop_after_once

            # 执行函数
            booster.load_collect()

        # 验证 pod_data 中数值是否正确更新
        pod_info = booster.pod_data[pod_path]
        self.assertEqual(len(pod_info['half_hour_avg']), 1)
        self.assertAlmostEqual(pod_info['half_hour_avg'][0][2], 0.6)
        self.assertEqual(pod_info['qualified'], True)
        self.assertEqual(pod_info['count'], 0)
        self.assertEqual(pod_info['sum'], 0)
        self.assertEqual(pod_info['last_processed_minute'], 0)
        booster.stop()

    @patch("time.sleep")
    def test_load_collect_unqualified_and_missing_data(self, mock_sleep):
        booster = QuotaBooster(forecast=False)
        booster.running = True
        booster.monitor_interval = 0.01
        booster.queue_max_len = 1
        booster.load_collect_thread = MagicMock()

        pod1 = "/pod/1"
        pod2 = "/pod/2"
        booster.cpu_queue_dict = {
            pod1: {
                util.CPU_UTIL: [0.4]
            }
            # pod2 故意不出现在 cpu_queue_dict 来测试 update=False -> qualified=False
        }

        now = datetime(2025, 8, 5, 10, 30, tzinfo=timezone.utc) + timedelta(hours=8)
        booster.pod_data[pod1]['start_time'] = now - timedelta(seconds=1800)
        booster.pod_data[pod2]['start_time'] = now - timedelta(seconds=1800)
        booster.pod_data[pod1]['qualified'] = True
        booster.pod_data[pod2]['qualified'] = True
        booster.pod_data[pod2]['update'] = False

        with patch("waas_booster.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            mock_datetime.timezone = timezone
            mock_datetime.timedelta = timedelta

            def stop_after_once(*args, **kwargs):
                booster.running = False
            mock_sleep.side_effect = stop_after_once

            booster.load_collect()

        # pod1 有数据，qualified = True
        self.assertEqual(len(booster.pod_data[pod1]['half_hour_avg']), 1)
        self.assertIsNotNone(booster.pod_data[pod1]['half_hour_avg'][0][2])

        # pod2 无 update，qualified = False，half_hour_avg 追加 None
        self.assertEqual(booster.pod_data[pod2]['qualified'], False)
        self.assertEqual(booster.pod_data[pod2]['update'], True)  # 被设置为了 True
        self.assertEqual(len(booster.pod_data[pod2]['half_hour_avg']), 0)
        booster.stop()


if __name__ == '__main__':
    unittest.main()