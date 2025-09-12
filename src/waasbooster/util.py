# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import os
import re
import time
import argparse
import boost_log as logging


WAAS_BOOSTER_MANAGER = '/var/run/waasbooster_manager/'
DATA_PATH = '/var/waasbooster/'
LOG_LEVEL_INFO = 'INFO'
LOG_LEVEL_DEBUG = 'DEBUG'
LOG_LEVEL_ERROR = 'ERROR'
LOG_LEVEL_WARNING = 'WARNING'
LOG_LEVEL_CRITICAL = 'CRITICAL'
LOG_LEVEL_LIST = ['INFO', 'DEBUG', 'ERROR', 'WARNING', 'CRITICAL']
GLOBAL_LOG_LEVEL = 'DEBUG'
LOG_PATH = '/var/log/waasbooster.log'
LOG_SAVE_PATH = '/var/log/'
LOG_NUM = 20
LOG_SIZE = 50

OVER_RESERVE_QUOTA = False
NOT_OVER_RESERVE_QUOTA = True
OG_QUOTA = 'og_quota'
AC_QUOTA = 'ac_quota'
BT_QUOTA = 'boost_quota'
CPUSET = 'cpuset'
CONTAINER_SHARES = 'container_shares'
CPU_UTIL = 'cpu_util'
QUOTA_UTIL = 'quota_util'
AVG_QUOTA_UTIL = 'avg_quota_util'
CGROUP_QUOTA = 'cpu.cfs_quota_us'
QUEUE_WEIGHT_RANGE = 3
EXPAND_MODE = 'expand'
SCALING_MODE = 'scaling'
CPU_SHARES = 'cpu.shares'
SYS_NODE_PATH = '/sys/devices/system/node'


def get_cpu_cgroup_mount_point():
    """获取CPU CGROUP的挂载点"""
    cpu_path = None
    cpuset_path = None
    with open('/proc/mounts', 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            fs_type, mount_point, options = parts[2], parts[1], parts[3]
            if fs_type == 'cgroup' and 'cpu' in options.split(','):
                cpu_path = mount_point
            if fs_type == 'cgroup' and 'cpuset' in options.split(','):
                cpuset_path = mount_point
    return cpu_path, cpuset_path


def get_numa_cpu_mapping():
    """获取NUMA节点和其对应的CPU列表的映射关系"""
    numa_nodes = {}
    sys_node_path = SYS_NODE_PATH
    if not os.path.exists(sys_node_path):
        raise OSError('NUMA not supported or /sys not accessible')
    for node_dir in os.listdir(sys_node_path):
        if node_dir.startswith('node'):
            node_id = int(node_dir[4:])
            cpulist_file = os.path.join(sys_node_path, node_dir, 'cpulist')
            with open(cpulist_file, 'r') as f:
                cpu_list = f.read().strip()
            numa_nodes.update({node_id: cpu_list})
    return numa_nodes


def get_cpuset_cgroup_mount_point():
    """获取CPUSET CGROUP的挂载点"""
    with open('/proc/mounts', 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            fs_type, mount_point, options = parts[2], parts[1], parts[3]
            if fs_type == 'cgroup' and 'cpuset' in options.split(','):
                return mount_point
    return None


def get_all_pids():
    """获取系统PID列表"""
    return [pid for pid in os.listdir('/proc') if pid.isdigit()]


def get_cgroup_path_for_pid(pid, cpu_mount, cgroup_key):
    """获取指定PID的cpu cgroup路径"""
    try:
        cgroup_path = file_check(pid, cpu_mount, cgroup_key)
        if cgroup_path:
            return cgroup_path
    except Exception as e:
        logging.debug('Fail to get %s cgroup path for %s', pid, e)
    return None


def file_check(pid, cpu_mount, cgroup_key):
    """检查指定PID的cgroup信息， 如果匹配cgroup key， 返回对应的cpu_mount路径"""
    with open(f'/proc/{pid}/cgroup', 'r') as f:
        for line in f:
            parts = line.strip().split(':')
            if len(parts) < 3:
                continue
            else:
                # 前两部分与剩余部分合并
                new_parts = parts[:2] + [':'.join(parts[2:])]
            _, controllers, path = new_parts
            if cgroup_key in controllers.split(',') and path.strip() is not None and path.strip() != '/':
                return os.path.join(cpu_mount, path.lstrip('/'))
    return None


def is_container_path(path):
    """判断是否为目标容器路径"""
    patterns = [
        r'docker',
        r'kubepods',
        r'containerd'
    ]
    return any(re.search(p, path) for p in patterns)


def check_container_cpuset_cpus(cpu_set_path):
    """判断容器是否NUMA亲和"""
    pod_nodes = None
    try:
        numa_nodes = get_numa_cpu_mapping()
        path = os.path.join(cpu_set_path, 'cpuset.cpus')
        if not os.path.exists(path):
            return False, pod_nodes
        with open(os.path.join(cpu_set_path, 'cpuset.cpus'), 'r') as f:
            container_cpu_num = f.read().strip()
        pod_results, pod_nodes = is_numa_multiple(container_cpu_num, numa_nodes)
        if pod_results:
            return True, pod_nodes
        else:
            return False, pod_nodes
    
    except Exception as e:
        raise Exception(f'check container cpuset.cpus error for: {e}') from e


def get_container_cgroups():
    """获取所有容器的CGROUP路径"""
    cpu_mount, cpuset_mount = get_cpu_cgroup_mount_point()
    if not cpu_mount:
        return [], []
    container_paths = []
    container_nodes = {}
    # 收集所有cgroup路径
    for pid in get_all_pids():
        path = get_cgroup_path_for_pid(pid, cpu_mount, 'cpu')
        cpu_set_path = get_cgroup_path_for_pid(pid, cpuset_mount, 'cpuset')
        if legal_cgroup_path(path, cpu_set_path, cpu_mount, container_paths):
            check_pod_valid, pod_nodes = check_container_cpuset_cpus(cpu_set_path)
            if (check_pod_valid and os.path.exists(os.path.join(path, 'cpu.cfs_quota_us'))
                and is_container_path(path)):
                container_paths.append(path)
                container_nodes.update({path: pod_nodes})

    return container_paths, container_nodes


def legal_cgroup_path(path, cpu_set_path, cpu_mount, container_paths):
    """检查给定路径是否合法"""
    if path and path != cpu_mount and path not in container_paths:
        if cpu_set_path:
            return True
        else:
            return False
    else:
        return False


def get_boosted_container_cgroups():
    """获取quota非-1的container cgroup路径"""
    container_paths, container_nodes = get_container_cgroups()
    boosted_container_path = []
    boosted_container_node = {}
    for path in container_paths:
        try:
            with open(os.path.join(path, 'cpu.cfs_quota_us'), 'r') as f:
                quota_value = f.read().strip()
                if quota_value != '-1':
                    boosted_container_path.append(path)
                    boosted_container_node.update({path: container_nodes.get(path)})
        except Exception as e:
            logging.warning("Fail to read container %s quota value for %s", path, e)
    return sorted(boosted_container_path), boosted_container_node


def get_container_info(container_path, info_name):
    info_value = None
    try:
        with open(os.path.join(container_path, info_name), 'r') as f:
            info_value = f.read().strip()
    except Exception as e:
        logging.warning('Fail to get container info for: %s', e)
    return info_value


def weighted_queue_sum(queue_data, queue_weight_list):
    if len(queue_data) != len(queue_weight_list) or not queue_data:
        return None
    else:
        sum_util = 0
        sum_weight = 0
        for i, v in enumerate(queue_data):
            if v is None:
                return None
            else:
                v_avg = v
            sum_util += v_avg * queue_weight_list[i]
            sum_weight += queue_weight_list[i]
        return sum_util / sum_weight if sum_weight != 0 else 0.0


def read_cpu_stats():
    try:
        cpu_stats = read_file()
        return cpu_stats
    except IOError:
        logging.warning('Fail to read /proc/stat')
        return None


def read_file():
    with open('/proc/stat', 'r') as f:
        for line in f:
            if line.startswith('cpu '):
                parts = line.split()
                user = int(parts[1])
                nice = int(parts[2])
                system = int(parts[3])
                idle = int(parts[4])
                iowait = int(parts[5])
                irq = int(parts[6])
                softirq = int(parts[7])
                steal = int(parts[8])
                guest = int(parts[9])
                guest_nice = int(parts[10])
                total = user + nice + system + idle + iowait + irq + softirq + steal + guest + guest_nice
                return {'idle': idle, 'total': total}
    return None


def get_cpu_usage(interval=1):
    # 第一次读取CPU统计信息
    initial_stats = read_cpu_stats()
    if initial_stats is None:
        return None
    
    initial_idle = initial_stats['idle']
    initial_total = initial_stats['total']

    # 等待指定时间间隔
    time.sleep(interval)

    # 第二次读取CPU统计信息
    final_stats = read_cpu_stats()
    if final_stats is None:
        return None
    
    final_idle = final_stats['idle']
    final_total = final_stats['total']

    # 计算CPU使用率
    total_diff = final_total - initial_total
    idle_diff = final_idle - initial_idle

    if total_diff == 0:
        return 0.0
    
    cpu_usage = ((total_diff - idle_diff) / total_diff) * 100
    return cpu_usage


def parse_cpu_affinity(affinity_str):
    cores = []
    if not affinity_str:
        return cores        # 如果输入为空， 返回空列表
    parts = affinity_str.split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                cores.extend(range(start, end + 1))
            except ValueError:
                logging.error(f'Invalid range format: {part}')
                continue
        else:
            try:
                cores.append(int(part))
            except ValueError:
                logging.error(f'Invalid cores number: {part}')
                continue
    return cores


def map_cores_to_numa(cores, numa_info):
    numa_nodes = set()
    for core in cores:
        for node, range_str in numa_info.items():
            start, end = map(int, range_str.split('-'))
            if start <= core <= end:
                numa_nodes.add(node)
                break
    return list(numa_nodes)


def is_numa_multiple(affinity_str, numa_info):
    cores = parse_cpu_affinity(affinity_str)
    nodes = map_cores_to_numa(cores, numa_info)
    valid_nodes = []

    # 检查是否所有核心都属于一个或多个完整的NUMA节点
    for node in nodes:
        node_range = numa_info[node]
        node_start, node_end = map(int, node_range.split('-'))
        # 检查该节点的所有核心是否都被包含在绑核范围内
        all_in = True
        for core in range(node_start, node_end + 1):
            if core not in cores:
                all_in = False
                break
        if all_in:
            valid_nodes.append(node)
        else:
            return False, []
            
    return True, valid_nodes


def str2bool(choice):
    if choice.lower() in ('true', 'false'):
        return choice.lower() == 'true'
    else:
        return argparse.ArgumentParser('Bool value expected')