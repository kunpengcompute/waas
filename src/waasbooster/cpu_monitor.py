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
import copy
import threading
from collections import deque
import math
import boost_log as logging
from util import weighted_queue_sum, CPU_UTIL, QUOTA_UTIL, AVG_QUOTA_UTIL, QUEUE_WEIGHT_RANGE, AC_QUOTA


class CpuMonitor:
    def __init__(self, over_load_cor=0.9, queue_max_len=15, delay_interval=10):
        self.running = True     # 线程运行的标志位
        self.over_load_cor = over_load_cor      # cpu负载超限系数
        self.queue_max_len = int(queue_max_len)     # 滑动窗口队列长度
        self.container_info_queue_dict = {}         
        self.delay_interval = delay_interval
        self.queue_weight_list = []
        self.lock = threading.Lock()

        for i in range(self.queue_max_len):
            self.queue_weight_list.append(math.exp((i+1) / self.queue_max_len * QUEUE_WEIGHT_RANGE))

    @staticmethod
    def get_cpu_usage(path):
        """读取CPU累计使用时间"""
        try:
            with open(os.path.join(path, 'cpuacct.usage'), 'r') as f:
                return int(f.read().strip())
        except Exception:
            return None

    @staticmethod
    def get_cpu_limits(path):
        """获取CPU配额限制"""
        try:
            with open(os.path.join(path, 'cpu.cfs_quota_us'), 'r') as f:
                quota = int(f.read().strip())
            with open(os.path.join(path, 'cpu.cfs_period_us'), 'r') as f:
                period = int(f.read().strip())
            return quota, period
        except Exception:
            return -1, 100000

    def get_container_info_queue_dict(self):
        with self.lock:
            container_info_queue_dict = copy.copy(self.container_info_queue_dict)
        return container_info_queue_dict

    def stop(self):
        self.running = False

    def run(self, containers, interval):
        if not containers:
            logging.warning('No pod cgroup to find.')
            return
        
        # 初始采样
        samples = {}
        for path in containers:
            usage = self.get_cpu_usage(path)
            if usage is not None:
                samples[path] = (usage, time.time())
                with self.lock:
                    self.container_info_queue_dict.update({path: {
                                                            CPU_UTIL: deque(maxlen=self.queue_max_len),
                                                            QUOTA_UTIL: deque(maxlen=self.queue_max_len),
                                                            AVG_QUOTA_UTIL: None,
                                                            AC_QUOTA: None}})
        time.sleep(interval)

        while self.running:
            _ = self.cpu_util_cal(containers, samples, interval)
        
        logging.debug('cpu monitor stop.')

    def cpu_util_cal(self, containers, samples, interval):
        for path in containers:
            current_usage = self.get_cpu_usage(path)
            current_time = time.time()

            if current_usage is None or path not in samples:
                continue

            prev_usage, prev_time = samples[path]
            delta_time = current_time - prev_time

            if delta_time <= 0:
                continue
                
            # 绝对利用率计算
            delta_usage_ns = current_usage - prev_usage
            absolute_util = (delta_usage_ns / 1e9) / delta_time * 100

            # 获取配额信息
            quota, period = self.get_cpu_limits(path)
            relative_util = None

            if quota != -1 and period > 0:
                # 相对于quota配额利用率
                max_available = (quota / period) * delta_time * 1e9
                if max_available > 0:
                    relative_util = (delta_usage_ns / max_available) * 100
                else:
                    relative_util = 0.0

            try:
                with self.lock:
                    self.container_info_queue_dict[path][CPU_UTIL].append(absolute_util)
                    self.container_info_queue_dict[path][QUOTA_UTIL].append(relative_util)
                    quota_util = self.container_info_queue_dict[path].get(QUOTA_UTIL)
                    avg_util = weighted_queue_sum(quota_util, self.queue_weight_list)
                    self.container_info_queue_dict[path].update({AVG_QUOTA_UTIL: avg_util})
                    self.container_info_queue_dict[path].update({AC_QUOTA: quota})
            except KeyError as ke:
                raise KeyError(f'cpu monitor error for: {ke}') from ke
            except Exception as e:
                raise Exception(f'cpu monitor error for: {e}') from e

            # 更新采样数据
            samples[path] = (current_usage, current_time)

        # 等待下一个采样周期
        time.sleep(interval)
        
        return self.container_info_queue_dict