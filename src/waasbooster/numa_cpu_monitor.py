# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import os
import copy
import time
import threading
from collections import deque
import boost_log as logging
import util


class NUMAMonitor:
    def __init__(self, interval=1, queue_max_len=5):
        self.interval = interval
        self.numa_util_dict = {}
        self.running = True
        self.queue_max_len = queue_max_len
        self.lock = threading.Lock()

    @staticmethod
    def parse_cpu_range(cpu_range_str):
        cpus = []
        for part in cpu_range_str.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                cpus.extend(range(start, end+1))
            else:
                cpus.append(int(part))
        return cpus

    @staticmethod
    def _parse_stat_line(line):
        parts = line.split()
        total = sum(map(int, parts[1:8]))
        idle = int(parts[4])
        return {'total': total, 'idle': idle}

    def get_numa_cpu_mapping(self):
        numa_nodes = {}
        sys_node_path = util.SYS_NODE_PATH
        if not os.path.exists(sys_node_path):
            raise Exception('NUMA not supported or /sys not accessible')
        for node_dir in os.listdir(sys_node_path):
            if node_dir.startswith('node'):
                node_id = int(node_dir[4:])
                cpulist_file = os.path.join(sys_node_path, node_dir, 'cpulist')
                with open(cpulist_file, 'r') as f:
                    cpu_list = f.read().strip()
                numa_nodes[node_id] = self.parse_cpu_range(cpu_list)
        return numa_nodes

    def get_cpu_utilization(self, interval=1):
        with open('/proc/stat', 'r') as f:
            first_measure = f.readlines()

            first_times = {}
            for line in first_measure:
                if line.startswith('cpu') and line[3].isdigit():
                    cpu = line.split()[0][3:]
                    parsed_line = self._parse_stat_line(line)
                    first_times[cpu] = parsed_line
        
        time.sleep(interval)

        with open('/proc/stat', 'r') as f:
            second_measure = f.readlines()

            second_times = {}
            for line in second_measure:
                if line.startswith('cpu') and line[3].isdigit():
                    cpu = line.split()[0][3:]
                    parsed_line = self._parse_stat_line(line)
                    second_times[cpu] = parsed_line

        utilizations = {}
        for cpu in first_times:
            if cpu not in second_times:
                continue
            t1 = first_times[cpu]
            t2 = second_times[cpu]
            total_diff = t2['total'] - t1['total']
            idle_diff = t2['idle'] - t1['idle']
            utilization = 100.0 * (1.0 - idle_diff / total_diff) if total_diff != 0 else 0.0
            utilizations[int(cpu)] = utilization
        
        return utilizations

    def run(self):
        numa_cpus = self.get_numa_cpu_mapping()
        with self.lock:
            self.numa_util_dict.update({'all': deque(maxlen=self.queue_max_len)})
            for numa_key, _ in numa_cpus.items():
                self.numa_util_dict.update({numa_key: deque(maxlen=self.queue_max_len)})
        while self.running:
            _ = self.update_numa_util_dict(numa_cpus)

    def stop(self):
        self.running = False
        logging.debug('NUMA cpu util monitor stop')
    
    def get_numa_cpu_dict(self):
        try:
            with self.lock:
                numa_cpu_dict = copy.copy(self.numa_util_dict)
        except Exception as e:
            logging.warning('NUMA cpu dict get failed for: %s', e)
            numa_cpu_dict = {}
        return numa_cpu_dict

    def update_numa_util_dict(self, numa_cpus):
        try:
            cpu_utils = self.get_cpu_utilization(interval=1)
            all_avg = sum(cpu_utils.values()) / len(cpu_utils) if len(cpu_utils) != 0 else 0
            with self.lock:
                self.numa_util_dict['all'].append(round(all_avg, 2))
                for node_id, cpus in numa_cpus.items():
                    total = sum(cpu_utils.get(cpu, 0) for cpu in cpus)
                    avg = total / len(cpus) if cpus else 0
                    self.numa_util_dict[node_id].append(round(avg, 2))
        except KeyError as ke:
            logging.warning('NUMA cpu util monitor failed for: %s', ke)
        except Exception as e:
            logging.warning('NUMA cpu util monitor failed for: %s', e)
            raise Exception('NUMA cpu util monitor failed for: {}'.format(e)) from e
        
        return self.numa_util_dict