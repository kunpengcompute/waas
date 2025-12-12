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
import signal
import time
import json
import threading
import argparse

import util
import waas_log as logging
from metric_monitor import MetricMonitor
from numa_transfer import NumaTransfer

WC = None
WC_RUNNING = True


class WaasCodeploy:
    def __init__(self) -> None:
        self.pid_file = util.PID_FILE
        self.pid_map = {}
        self.transfer_pid_map = {}
        self.init_pid_info = {}
        self.init_cgroup_info = {}
        self.init_pid_info_file = util.PID_INFO_FILE
        self.target_process_list = util.PROC_LIST
        self.metric_monitor = MetricMonitor(util.EVT_LIST)
        self.metric_monitor_thread = None
        self.running = True
        self.numa_transfer_knob = util.NUMA_TRANSFER
        self.numa_transfer_last_time = time.time()
        self.base_mount, _ = util.find_cpuset_mountpoint()

    @staticmethod
    def update_pid_core(pid_map, pid_core_dict):
        for _, pids in pid_map.items():
            if pids:
                for pid in pids:
                    pid_core_dict.update({str(pid): sorted(list(os.sched_getaffinity(pid)))})
        return pid_core_dict

    def init_bind_core_record(self, init_pid_info):
        try:
            fd = os.open(self.init_pid_info_file, os.O_WRONLY | os.O_CREAT, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as file:
                file.write(json.dumps(init_pid_info, indent=4))
        except Exception as e:
            logging.warning('Init pid info record failed for: %s', e)
            return False
        return True

    def init_bind_core_load(self):
        init_pid_info = {'pid':{}, 'cgroups':{}}
        if os.path.exists(self.init_pid_info_file):
            try:
                with open(self.init_pid_info_file, 'r', encoding='utf-8') as file:
                    init_pid_info = json.load(file)
            except Exception as e:
                logging.warning('Init quota load failed for: %s', e)
        return init_pid_info

    def init_service(self):
        if os.path.exists(self.pid_file):
            try:
                os.unlink(self.pid_file)
            except OSError as oe:
                logging.warning('Cannot remove existing PID file {}, {}'.format(self.pid_file, str(oe)))
                return False
        try:
            dir_name = os.path.dirname(self.pid_file)
            if not os.path.exists(dir_name):
                os.makedirs(dir_name)
            
            with os.fdopen(os.open(self.pid_file, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600), 'w') as f:
                f.write("%d" % os.getpid())
                logging.debug('Waas codeploy pid write finished')
            return True

        except (OSError, IOError) as error:
            logging.error('Cannot write the PID to {}: {}'.format(self.pid_file, str(error)), exc_info=True)
            return False
        except Exception as e:
            logging.error('pid create error for: %s', e)
            return False
        
    def run(self) -> None:
        while self.running:
            try:
                self.codeploy()
            except Exception as e:
                logging.warning('Waas codeploy exit error occurred for: %s', e)

    def stop(self) -> None:
        self.running = False
        _ = self.stop_monitor()
        self.restore()
        self.cleanup()

    def cleanup(self):
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            if os.path.exists(self.init_pid_info_file):
                os.remove(self.init_pid_info_file)
        except Exception as e:
            logging.warning('Cleanup failed for: %s', e)

    def get_target_pid(self, target_process_name: str) -> dict:
        pid_map = util.find_pids_by_identifiers(target_process_name)
        return pid_map

    def get_thread_bind_core(self, pid_map: dict) -> dict:
        pid_core_dict = {}
        if not pid_map:
            logging.info("Pid map is empty")
        else:
            pid_core_dict = self.update_pid_core(pid_map, pid_core_dict)
        return pid_core_dict

    def get_pid_croup_core(self, pid_map: dict) -> dict:
        pid_cgroup_core = {}
        if not pid_map:
            logging.info("Pid map is empty")
        else:
            proc_info = util.inspect_processes(self.target_process_list, pid_map)
            pid_cgroup_core = util.group_pids_by_cpuset(proc_info)
        return pid_cgroup_core

    def bind_physical_core(self, pid_cgroup_core: dict) -> dict:
        bind_result = {}
        pid_core_tobe_bind = util.calculate_pid_bind_core(pid_cgroup_core)
        for pid, cpu_list in pid_core_tobe_bind.items():
            spid = util.get_threads_psutil(pid)
            result = util.set_affinity(spid, cpu_list)
            bind_result.update({pid: result})
        return bind_result

    def stop_monitor(self):
        if self.metric_monitor:
            self.metric_monitor.stop()
        if self.metric_monitor_thread:
            self.metric_monitor_thread.join()
        while self.metric_monitor_thread.is_alive():
            time.sleep(util.WAIT_INTERVAL)
        return True

    def refresh_monitor(self):
        _ = self.stop_monitor()
        self.metric_monitor = MetricMonitor(util.EVT_LIST)
        cgroup_list = self.get_cgroup_list(self.pid_map)
        logging.info("cgroup_list is %s", cgroup_list)
        self.metric_monitor_thread = threading.Thread(target=self.metric_monitor.run,
                                            args=(cgroup_list, util.MONITOR_DURATION))
        self.metric_monitor_thread.start()

    def codeploy(self):
        first_flag = True
        # 初始化pid记录
        self.pid_map = self.get_target_pid(util.PROC_LIST)
        init_pid_info = self.get_thread_bind_core(self.pid_map)
        past_info = self.init_bind_core_load()
        if not self.init_pid_info.get(util.PID):
            self.init_pid_info.update({util.PID: {**init_pid_info, **past_info.get(util.PID)}})
            _ = self.init_bind_core_record(self.init_pid_info)
        # 初始化cgroup记录
        self.transfer_pid_map = self.get_target_pid(util.NUMA_TRANSFER_PROC_LIST)
        transfer_cgroup_list = self.get_cgroup_list(self.transfer_pid_map)
        init_transfer_cgroup_dict = self.get_cgroup_cpuset(transfer_cgroup_list)
        if not self.init_pid_info.get(util.CGROUP):
            self.init_pid_info.update({util.CGROUP: {**init_transfer_cgroup_dict, **past_info.get(util.CGROUP)}})
            _ = self.init_bind_core_record(self.init_pid_info)

        init_pid_cgroup_core = self.get_pid_croup_core(self.pid_map)
        cgroup_list = self.get_cgroup_list(self.pid_map)
        logging.info("cgroup_list is %s", cgroup_list)
        self.metric_monitor_thread = threading.Thread(target=self.metric_monitor.run,
                                                       args=(cgroup_list, util.MONITOR_DURATION))
        self.metric_monitor_thread.start()
        time.sleep(util.MONITOR_DURATION)

        while self.running:
            _ = self.numa_transfer()
            pid_map = self.get_target_pid(util.PROC_LIST)
            pid_info = self.get_thread_bind_core(pid_map)
            pid_cgroup_core = self.get_pid_croup_core(pid_map)
            if pid_map != self.pid_map or pid_cgroup_core != init_pid_cgroup_core or pid_info != init_pid_info:
                transfer_pid_map = self.get_target_pid(util.NUMA_TRANSFER_PROC_LIST)
                transfer_cgroup_list = self.get_cgroup_list(transfer_pid_map)
                cgroup_info = self.get_cgroup_cpuset(transfer_cgroup_list)
                self.pid_map = pid_map
                init_pid_cgroup_core = pid_cgroup_core
                _ = self.refresh_init_pid_info(pid_info, cgroup_info)
                self.refresh_monitor()
                _ = self.bind_physical_core(pid_cgroup_core)
                init_pid_info = self.get_thread_bind_core(self.pid_map)
                first_flag = True
            if self.cgroup_metric_overhead():
                if first_flag:
                    first_flag = False
                    _ = self.bind_physical_core(pid_cgroup_core)
                    init_pid_info = self.get_thread_bind_core(self.pid_map)

            time.sleep(util.WORK_INTERVAL)

    def numa_transfer(self):
        cgroup_move_dict = {}
        if self.numa_transfer_knob:
            numa_transfer_current_time = time.time()
            self.transfer_pid_map = self.get_target_pid(util.NUMA_TRANSFER_PROC_LIST)
            cgroup_list = self.get_cgroup_list(self.transfer_pid_map)
            cgroup_dict = self.get_cgroup_cpuset(cgroup_list)
            logging.info('Transfer cgroup list is %s', cgroup_list)
            
            if numa_transfer_current_time - self.numa_transfer_last_time > 5 * util.WORK_INTERVAL:
                transfer = NumaTransfer(interval=util.MONITOR_DURATION)
                cgroup_move_dict = transfer.balance_load(cgroup_list)
                self.numa_transfer_last_time = numa_transfer_current_time
            if cgroup_move_dict:
                _ = self.refresh_init_pid_info(None, cgroup_dict)

        return cgroup_move_dict

    def get_cgroup_cpuset(self, cgroup_list):
        cgroup_dict = {}
        if not cgroup_list:
            return cgroup_dict
        else:
            for cgroup in cgroup_list:
                cgroup_dict.update({cgroup: [util.read_cpuset_from_cgroup(self.base_mount, cgroup),
                                            util.read_cpumem_from_cgroup(self.base_mount, cgroup)]})
        return cgroup_dict

    def refresh_init_pid_info(self, pid_info, cgroup_info) -> dict:
        if pid_info:
            for pid, info in pid_info.items():
                if pid not in self.init_pid_info.get(util.PID).keys():
                    self.init_pid_info[util.PID].update({pid: info})
        if cgroup_info:
            for cgroup, cg_info in cgroup_info.items():
                if cgroup not in self.init_pid_info.get(util.CGROUP).keys():
                    self.init_pid_info[util.CGROUP].update({cgroup: cg_info})
        _ = self.init_bind_core_record(self.init_pid_info)
        return self.init_pid_info

    def get_cgroup_metric(self) -> dict:
        cgroup_metric_dict = self.metric_monitor.get_monitor_cgroup_metric()
        return cgroup_metric_dict

    def cgroup_metric_overhead(self) -> bool:
        cgroup_metric_dict = self.get_cgroup_metric()
        if not cgroup_metric_dict:
            _ = self.refresh_monitor()
            time.sleep(util.MONITOR_DURATION)
            cgroup_metric_dict = self.get_cgroup_metric()
        for cgroup, cgroup_info in cgroup_metric_dict.items():
            monitor_metric = cgroup_info.get(util.OVERLOAD_METRIC).get(util.METRIC_INDEX)
            logging.debug("cgroup %s monitor_metric is: %s", cgroup, monitor_metric)
            if monitor_metric >= util.OVERLOAD_THRE:
                return True
        return False

    def get_cgroup_list(self, pid_map):
        cgroup_list = []
        for _, pids in pid_map.items():
            if not pids:
                continue
            for pid in pids:
                cgroup_name = util.parse_proc_cgroup(pid).get(util.CPUSET)
                if cgroup_name not in cgroup_list:
                    cgroup_list.append(cgroup_name)
        
        return cgroup_list

    def restore(self) -> None:
        if not self.init_pid_info:
            return
        if self.init_pid_info.get(util.CGROUP):
            for cg, cg_info in self.init_pid_info.get(util.CGROUP).items():
                cg_result = util.set_cgroup_cpuset(self.base_mount, cg, cg_info)
            logging.info("Cgroup init cpuset restored.")
        if self.init_pid_info.get(util.PID):
            for pid, cpu_list in self.init_pid_info.get(util.PID).items():
                spid = util.get_threads_psutil(pid)
                result = util.set_affinity(spid, cpu_list)
            logging.info("Pid init affinity restored.")
        return


def sigterm_handler(signum, frame):
    global WC
    global WC_RUNNING
    logging.info('Waas codeploy start to exit')
    try:
        WC.stop()
    except Exception as e:
        logging.error('Waas codeploy stop failed for %s', e)
    WC_RUNNING = False
    logging.info('Waas codeploy exitted')

signal.signal(signal.SIGTERM, sigterm_handler)


def codeploy_param_parser():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Waas codeploy service')
    parser.add_argument('--target', type=str, default='SPECjbb', help='target proc')
    args = parser.parse_args()

    return args

def waas_codeploy_main():
    global WC
    global WC_RUNNING
    log_level = util.LOG_LEVEL_INFO
    args = codeploy_param_parser()

    try:
        # 初始化日志模块
        log_level
        logging.set_log_instance(log_level)
        logging.info('Initialize log module, log level set {}'.format(log_level))
        logging.info('Version: 1.0.0')
        # 创建管理文件
        os.makedirs(util.WAAS_CODEPLOY_MANAGER, exist_ok=True)
        WC = WaasCodeploy(
        )
        WC.init_service()
        cpu_thread = threading.Thread(target=WC.run)
        cpu_thread.start()
        logging.info('Waas codeploy service start')
        while WC_RUNNING:
            if not WC_RUNNING:
                break
            time.sleep(1)
    except Exception as e:
        logging.error('Waas codeploy stopped for: %s', e)


if __name__ == '__main__':
    waas_codeploy_main()