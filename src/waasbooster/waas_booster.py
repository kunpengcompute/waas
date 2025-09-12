# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import os
import shutil
import signal
import time
import copy
import json
import threading
import argparse
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from cpu_monitor import CpuMonitor

from quota_updater import quota_updater
from quota_calculator import PIDController
import boost_log as logging
from quota_manager import QuotaManager
from data_collector import DataCollector
from numa_cpu_monitor import NUMAMonitor
from load_predictor import get_forecast_load
import util
from util import get_boosted_container_cgroups, get_container_info, AC_QUOTA, AVG_QUOTA_UTIL, CGROUP_QUOTA, \
                 EXPAND_MODE, SCALING_MODE, BT_QUOTA, str2bool

QB = None
QB_RUNNING = True


class QuotaBooster:
    def __init__(self, monitor_interval=0.1, queue_max_len=15, refresh_interval=60, over_load_threshold=0.9,
                 down_load_threshold=0.3, expand_cor=1.2, scaling_cor=0.9, boost_interval=10, unboost_interval=30,
                 max_expand_limit=3.0, min_scaling_limit=1.0, data_collect=False, data_collector_interval=600,
                 data_monitor_interval=1, numa_balance_interval=10, forecast=True):
        self.pid_file = os.path.join(util.WAAS_BOOSTER_MANAGER, 'waasbooster.pid')
        self.init_quota_file = os.path.join(util.WAAS_BOOSTER_MANAGER, 'init_quota.json')
        self.running = True
        self.monitor_interval = monitor_interval
        self.queue_max_len = queue_max_len
        self.refresh_interval = refresh_interval
        self.over_load_threshold = over_load_threshold
        self.down_load_threshold = down_load_threshold
        self.expand_cor = expand_cor
        self.scaling_cor = scaling_cor
        self.boost_interval = boost_interval
        self.unboost_interval = unboost_interval
        self.max_expand_limit = max_expand_limit
        self.min_scaling_limit = min_scaling_limit
        self.numa_balance_interval = numa_balance_interval
        self.forecast = forecast
        self.check_init_param()

        self.cpu_queue_dict = {}
        self.boost_pod_record_dict = {}
        self.data_collect = data_collect
        self.cpu_monitor, self.cpu_monitor_thread = None, None
        self.data_collector_interval = data_collector_interval
        self.data_monitor_interval = data_monitor_interval
        self.container_update_queue = {}
        self.quota_cal_mode = 'cor'
        self.pid_dict = {}
        self.dt = 0.1
        self.pod_og_quota = {}
        self.quota_manager = None
        self.lock = threading.Lock()
        self.data_collector, self.data_collector_thread = None, None
        self.numa_balance_last_time = time.time()
        self.numa_balance_current_time = None
        self.sleep_interval = 0.1
        self.last_forecast_time = None
        self.pod_data = defaultdict(lambda: {'sum': 0, 'count': 0, 'last_processed_minute': None, 
                                             'half_hour_avg': deque(maxlen=7*48), 
                                             'start_time': None, 'update': False, 'qualified': True})
        try: 
            self.pod_path, self.pod_nodes = self.get_all_pod()
            self.pod_og_quota = self.get_pod_og_quota()
            self.numa_monitor = NUMAMonitor()
            self.numa_monitor_thread = threading.Thread(target=self.numa_monitor.run)
            self.numa_monitor_thread.start()
            if self.forecast:
                self.load_collect_thread = threading.Thread(target=self.load_collect)
                self.load_collect_thread.start()
        except Exception as e:
            logging.error('Init error occurred for %s', e)
            raise Exception(f'Init error occurred for: {e}') from e

    @staticmethod
    def get_all_pod():
        pod_cgroup_path, pod_nodes = get_boosted_container_cgroups()
        logging.debug('All monitored pod: %s', pod_cgroup_path)
        return pod_cgroup_path, pod_nodes

    @staticmethod
    def quota_set(pod_update_quota_dict):
        quota_response = None
        if pod_update_quota_dict:
            for pod_path, pod_quota in pod_update_quota_dict.items():
                if pod_quota.get(BT_QUOTA) != pod_quota.get(AC_QUOTA):
                    quota_response = quota_updater(pod_path, pod_quota.get(BT_QUOTA))
        return quota_response

    def check_init_param(self):
        """初始化参数验证"""
        if not (0 <= self.over_load_threshold <= 1):
            raise ValueError('over_load_threshold must be between 0 and 1')
        if not (0 <= self.down_load_threshold <= 1):
            raise ValueError('down_load_threshold must be between 0 and 1')
        if self.expand_cor <= 1:
            raise ValueError('expand_cor must be greater than 1')
        if self.scaling_cor <= 0 or self.scaling_cor > 1:
            raise ValueError('scaling_cor must be between 0 and 1')
        if self.max_expand_limit < 1:
            raise ValueError('max_expand_limit must be greater than 1')
        if self.min_scaling_limit <= 0 or self.min_scaling_limit > 1:
            raise ValueError('min_scaling_limit must be between 0 and 1')
        if self.boost_interval <= self.queue_max_len * self.monitor_interval:
            raise ValueError('boost_interval must be greater than monitor_interval * {}'.format(self.queue_max_len))
        if self.unboost_interval <= self.queue_max_len * self.monitor_interval:
            raise ValueError('unboost_interval must be greater than monitor_interval * {}'.format(self.queue_max_len))
        if self.queue_max_len <= 10:
            raise ValueError('queue_max_len must be greater than 10')
        if self.forecast:
            logging.info('Pod forecast function turn on')
        elif not self.forecast:
            logging.info('Pod forecast function turn off')

    def init_service(self):
        self.write_pid_file()

    def write_pid_file(self):
        if os.path.exists(self.pid_file):
            try:
                os.unlink(self.pid_file)
            except OSError as oe:
                logging.warning('cannot remove existing PID file {}, {}'.format(self.pid_file, str(oe)))

        try:
            dir_name = os.path.dirname(self.pid_file)
            if not os.path.exists(dir_name):
                os.makedirs(dir_name)
            
            with os.fdopen(os.open(self.pid_file, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600), 'w') as f:
                f.write("%d" % os.getpid())
                logging.debug('pid write finished')
        
        except (OSError, IOError) as error:
            logging.error('cannot write the PID to {}: {}'.format(self.pid_file, str(error)), exc_info=True)
        except Exception as e:
            logging.error('pid create error for: %s', e)
        
    def run(self):
        try:
            self.quota_manager = QuotaManager()
            self.monitor_container()
            self.restore_init_quota()
            self.cleanup()
        except Exception as e:
            logging.error('cpu booster run error occurred for %s', e)
            raise Exception(f'cpu booster error for: {e}') from e
        logging.info('Waas booster exitting...')

    def stop(self):
        self.running = False
        self.cpu_util_queue_stop()
        if self.data_collect:
            self.data_collector.stop()
            self.data_collector_thread.join()
        if self.numa_monitor:
            self.numa_monitor.stop()
        if self.numa_monitor_thread:
            self.numa_monitor_thread.join()
        if self.load_collect_thread:
            self.load_collect_thread.join()
    
    def init_quota_record(self, quota_dict):
        try:
            with open(self.init_quota_file, 'w', encoding='utf-8') as file:
                file.write(json.dumps(quota_dict, indent=4))
        except Exception as e:
            logging.warning('Init quota record failed for: %s', e)
            return False
        return True

    def init_quota_load(self):
        init_quota = {}
        if not os.path.exists(self.init_quota_file):
            return init_quota
        else:
            try:
                with open(self.init_quota_file, 'r', encoding='utf-8') as file:
                    init_quota = json.load(file)
            except Exception as e:
                logging.warning('Init quota load failed for: %s', e)
            return init_quota

    def cleanup(self):
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            if os.path.exists(self.init_quota_file):
                os.remove(self.init_quota_file)
        except Exception as e:
            logging.warning('Cleanup failed for: %s', e)
        
    
    def monitor_container(self):
        self.cpu_util_queue_start()
        if self.data_collect:
            self.data_collector = DataCollector(self)
            self.data_collector_thread = threading.Thread(target=self.data_collector.collect_data)
            self.data_collector_thread.start()
        start_time = time.time()
        while self.running:
            current_time = time.time()
            if current_time - start_time >= self.refresh_interval:
                start_time = current_time
                self.refresh_pod_path()

            pod_update_quota_dict = {}
            numa_balance_dict = self.numa_balance()
            self.cpu_queue_dict = self.get_cpu_util_queue()
            pod_forecast = self.load_forecast()
            # 检测是否存在pod符合quota调整条件
            pod_update_quota_dict = self.check_pod_status(self.cpu_queue_dict, pod_update_quota_dict)
            # 整体资源调整申请管理
            if pod_update_quota_dict or numa_balance_dict:
                numa_cpu_util_dict = self.numa_monitor.get_numa_cpu_dict()
                logging.debug('numa cpu util dict is %s', numa_cpu_util_dict)
                pod_update_quota_dict = self.quota_manager.quota_approval(pod_update_quota_dict,
                                                                          self.boost_pod_record_dict,
                                                                          numa_cpu_util_dict,
                                                                          self.pod_nodes,
                                                                          pod_forecast)
                pod_update_quota_dict = {**numa_balance_dict, **pod_update_quota_dict}
            
            if pod_update_quota_dict:
                # quota调整值下发
                self.quota_set(pod_update_quota_dict)
                # 记录
                for pod_path, pod_info in pod_update_quota_dict.items():
                    self.boost_pod_record_dict.update({pod_path: {
                        BT_QUOTA: pod_info.get(BT_QUOTA),
                        util.OG_QUOTA: self.pod_og_quota.get(pod_path)
                    }})
                logging.debug('pod boost dict is %s', self.boost_pod_record_dict)
            time.sleep(self.sleep_interval)

    def check_pod_status(self, cpu_queue_dict, pod_update_quota_dict):
        for container_path, container_info in cpu_queue_dict.items():
            quota_update_value = self.calculate_container_quota(container_path, container_info)
            if quota_update_value:
                pod_update_quota_dict.update({
                    container_path: {
                        BT_QUOTA: quota_update_value,
                        AC_QUOTA: container_info.get(AC_QUOTA)
                    }
                })
        return pod_update_quota_dict

    def refresh_pod_path(self):
        init_quota_record = False
        logging.debug('start refresh pod path')
        pod_path, self.pod_nodes = self.get_all_pod()
        if pod_path != self.pod_path:
            logging.info('pod monitor refresh due to pod change')
            for path in pod_path:
                if path not in self.pod_path:
                    logging.info('new pod %s is being monitored', path)
                    self.pod_og_quota.update({path: int(get_container_info(path, CGROUP_QUOTA))})
                    init_quota_record = True
            self.pod_path = pod_path
            # 停止监控
            try:
                if self.cpu_monitor:
                    self.cpu_monitor.stop()
                if self.cpu_monitor_thread:
                    self.cpu_monitor_thread.join()
                while self.cpu_monitor_thread.is_alive():
                    time.sleep(self.sleep_interval)
            except Exception as e:
                logging.error(f'failed to stop CPU monitor: {e}')
            # 启动新队列
            self.cpu_util_queue_start()
        if init_quota_record:
            _ = self.init_quota_record(self.pod_og_quota)
        logging.debug('finish refresh pod path')
        
        return pod_path

    def cpu_util_queue_start(self):
        try:
            self.cpu_monitor = CpuMonitor(self.over_load_threshold, self.queue_max_len)
            self.cpu_monitor_thread = threading.Thread(target=self.cpu_monitor.run,
                                                       args=(self.pod_path, self.monitor_interval))
            self.cpu_monitor_thread.start()
        except Exception as e:
            logging.error('cpu monitor start error occurred for: %s', e)
            raise Exception(f'cpu monitor start failed for {e}') from e
        
        return self.cpu_monitor

    def cpu_util_queue_stop(self):
        try:
            if self.cpu_monitor:
                self.cpu_monitor.stop()
            if self.cpu_monitor_thread:
                self.cpu_monitor_thread.join()
        except Exception as e:
            logging.error('cpu util monitor stop error occurred for: %s', e)
            raise Exception(f'cpu monitor stop failed for {e}') from e

    def get_cpu_util_queue(self):
        return self.cpu_monitor.get_container_info_queue_dict()

    def update_container_queue_time(self, path, interval):
        """判断容器是否可以扩缩容"""
        if path in self.container_update_queue.keys():
            if time.time() - self.container_update_queue.get(path) >= interval:
                self.container_update_queue.update({path: time.time()})
                return True
            else:
                return False
        else:
            self.container_update_queue.update({path: time.time()})
            return True
        
    def calculate_container_quota(self, container_path, container_info):
        quota_update_value = None
        try:
            if container_info.get(AVG_QUOTA_UTIL) is not None and \
                container_info.get(AVG_QUOTA_UTIL) >= self.over_load_threshold * 100:
                if self.update_container_queue_time(container_path, self.boost_interval):
                    quota_update_value = self.quota_calculate(container_path, EXPAND_MODE, container_info)
            elif container_info.get(AVG_QUOTA_UTIL) is not None and \
                container_info.get(AVG_QUOTA_UTIL) <= self.down_load_threshold * 100:
                if self.update_container_queue_time(container_path, self.unboost_interval):
                    quota_update_value = self.quota_calculate(container_path, SCALING_MODE, container_info)
            return quota_update_value
        
        except Exception as e:
            raise Exception(f'update container quota error for: {e}') from e
    
    def quota_calculate(self, container_path, mode, container_info):
        quota_update_value = container_info.get(AC_QUOTA)
        if self.quota_cal_mode == 'cor':
            if mode == EXPAND_MODE:
                expand_quota_value = self.expand_cor * container_info.get(AC_QUOTA)
                if expand_quota_value <= self.pod_og_quota.get(container_path) * self.max_expand_limit:
                    quota_update_value = expand_quota_value
                elif expand_quota_value > self.pod_og_quota.get(container_path) * self.max_expand_limit:
                    quota_update_value = self.pod_og_quota.get(container_path) * self.max_expand_limit
            elif mode == SCALING_MODE:
                scaling_quota_value = self.scaling_cor * container_info.get(AC_QUOTA)
                if scaling_quota_value >= self.pod_og_quota.get(container_path) * self.min_scaling_limit:
                    quota_update_value = scaling_quota_value
                elif scaling_quota_value < self.pod_og_quota.get(container_path) * self.min_scaling_limit:
                    quota_update_value = self.pod_og_quota.get(container_path) * self.min_scaling_limit
        elif self.quota_cal_mode == 'pid':
            if container_path not in self.pid_dict.keys():
                self.pid_dict.update({container_path: self.init_pid(container_path)})
            if mode == EXPAND_MODE:
                target_quota_value = self.expand_cor * container_info.get(AC_QUOTA)
            elif mode == SCALING_MODE:
                target_quota_value = self.scaling_cor * container_info.get(AC_QUOTA)
            quota_update_value = self.pid_dict.get(container_path).update(target_quota_value,
                                                                          container_info.get(AC_QUOTA), self.dt)
        return quota_update_value

    def init_pid(self, container_path):
        pid = PIDController(
            Kp=-1,
            Ki=0.01,
            Kd=0.1,
            max_output=self.max_expand_limit * self.pod_og_quota.get(container_path),
            min_output=self.min_scaling_limit * self.pod_og_quota.get(container_path)
        )
        return pid

    def restore_init_quota(self):
        if self.pod_path:
            for pod_path in self.pod_path:
                quota_response = quota_updater(pod_path, self.pod_og_quota.get(pod_path))
                if not quota_response:
                    logging.warning('Pod %s may fail to restore initial quota', pod_path)
        logging.info('restore pod init quota succeed')

    def get_pod_og_quota(self):
        init_quota_dict = self.init_quota_load()
        logging.debug('init_quota_dict is: %s', init_quota_dict)
        pod_og_quota = {}
        for path in self.pod_path:
            pod_og_quota.update({path: int(get_container_info(path, CGROUP_QUOTA))})
        self.pod_og_quota = {**pod_og_quota, **init_quota_dict}
        logging.debug('self.pod_og_quota is: %s', self.pod_og_quota)
        _ = self.init_quota_record(self.pod_og_quota)
        return self.pod_og_quota

    def numa_balance(self):
        """numa balance策略检测与执行"""
        pod_update_quota_dict = {}
        self.numa_balance_current_time = time.time()
        if self.numa_balance_current_time - self.numa_balance_last_time > self.numa_balance_interval:
            self.numa_balance_last_time = time.time()
            numa_cpu_util_dict = self.numa_monitor.get_numa_cpu_dict()
            pod_update_quota_dict = self.quota_manager.quota_approval({},
                                                                      self.boost_pod_record_dict,
                                                                      numa_cpu_util_dict,
                                                                      self.pod_nodes,
                                                                      {})
        return pod_update_quota_dict

    def load_forecast(self):
        pod_forecast = None
        current_time = datetime.now(tz=timezone.utc) + timedelta(hours=8)
        try:
            if current_time.hour == 0 and current_time.minute == 5 and self.forecast:
                if self.last_forecast_time is None:
                    self.last_forecast_time = current_time
                    return pod_forecast
                elif self.last_forecast_time.date() == current_time.date():
                    return pod_forecast
                else:
                    self.last_forecast_time = current_time
                    with self.lock:
                        pod_data = copy.copy(self.pod_data)
                    pod_forecast = get_forecast_load(pod_data)
                    logging.info('Pod forecast result is: %s', pod_forecast)
                    logging.info('Pod load avg data is: %s', pod_data)
                    return pod_forecast
            else:
                return pod_forecast
        except Exception as e:
            logging.warning('Load forecast skip for: %s', e)
            return pod_forecast


    def load_collect(self):
        """训练数据收集"""
        while self.running:
            current_time = datetime.now(tz=timezone.utc) + timedelta(hours=8)
            if self.cpu_queue_dict:
                _ = self.update_pod_data(current_time)
                for pod_path, pod_info in self.pod_data.items():
                    if not pod_info['update']:
                        self.pod_data[pod_path]['qualified'] = False
                    self.pod_data[pod_path]['update'] = True
            time.sleep(self.monitor_interval * self.queue_max_len)
            logging.debug(f'self.pod_data is: {self.pod_data}')
    
    def update_pod_data(self, current_time):
        for pod_path, pod_info in self.cpu_queue_dict.items():
            try:
                cpu_util = pod_info[util.CPU_UTIL]
                avg_cpu_util = sum(cpu_util) / len(cpu_util)
                self.pod_data[pod_path]['sum'] += avg_cpu_util
                self.pod_data[pod_path]['count'] += 1
                if self.pod_data[pod_path]['start_time'] is None:
                    self.pod_data[pod_path]['start_time'] = current_time
                self.pod_data[pod_path]['update'] = True
                
                if (current_time.minute == 0 or current_time.minute == 30) and \
                    self.pod_data[pod_path]['last_processed_minute'] != current_time.minute:
                    if self.pod_data[pod_path]['qualified'] and self.pod_data[pod_path]['count'] !=0 and \
                    (current_time - self.pod_data[pod_path]['start_time']).total_seconds() >= 1200:
                        avg_cpu_util_halfhour = self.pod_data[pod_path]['sum'] / self.pod_data[pod_path]['count']
                        self.pod_data[pod_path]['half_hour_avg'].append((self.pod_data[pod_path]['start_time'], 
                                                                         current_time, avg_cpu_util_halfhour))
                    else:
                        self.pod_data[pod_path]['half_hour_avg'].append((self.pod_data[pod_path]['start_time'], 
                                                                         current_time, None))
                    self.pod_data[pod_path]['sum'] = 0
                    self.pod_data[pod_path]['count'] = 0
                    self.pod_data[pod_path]['start_time'] = current_time
                    self.pod_data[pod_path]['qualified'] = True
                    self.pod_data[pod_path]['last_processed_minute'] = current_time.minute
            except Exception as e:
                logging.debug('collect data lacking: %s', e)
                continue
        return self.pod_data


def sigterm_handler(signum, frame):
    global QB
    global QB_RUNNING
    logging.info('Waas booster start to exit')
    try:
        QB.stop()
    except Exception as e:
        logging.error('Waas booster stop failed for %s', e)
    QB_RUNNING = False
    logging.info('Waas booster exitted')

signal.signal(signal.SIGTERM, sigterm_handler)


def booster_param_parser():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Waas booster service')
    parser.add_argument('--forecast', type=str2bool, choices=[True, False], default=True, help='load forecast on/off')
    args = parser.parse_args()

    return args


def cpu_booster_main():
    global QB
    global QB_RUNNING
    log_level = util.LOG_LEVEL_INFO
    args = booster_param_parser()

    try:
        # 初始化日志模块
        log_level
        logging.set_log_instance(log_level)
        logging.info('Initialize log module, log level set {}'.format(log_level))
        logging.info('Version: 1.0.0')
        # 创建管理文件
        os.makedirs(util.WAAS_BOOSTER_MANAGER, exist_ok=True)
        QB = QuotaBooster(
            forecast=args.forecast
        )
        QB.init_service()
        cpu_thread = threading.Thread(target=QB.run)
        cpu_thread.start()
        logging.info('Waas Booster service start')
        while QB_RUNNING:
            if not QB_RUNNING:
                break
            time.sleep(1)
    except Exception as e:
        logging.error('Waas booster stopped for: %s', e)


if __name__ == '__main__':
    cpu_booster_main()