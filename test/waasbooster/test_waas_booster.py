# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import unittest
from unittest import mock
from unittest.mock import patch, mock_open, MagicMock
import os
import json
import sys
import time
import threading
from collections import deque

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
from util import get_boosted_container_cgroups, get_container_info, AC_QUOTA, AVG_QUOTA_UTIL, CGROUP_QUOTA, \
                 EXPAND_MODE, SCALING_MODE, BT_QUOTA
from waas_booster import QuotaBooster

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


if __name__ == '__main__':
    unittest.main()

