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
import re
import psutil
import re
from typing import List, Dict, Optional, Tuple, Set

import waas_log as logging


# 自定义开关和参数
# NUMA迁移功能
NUMA_TRANSFER = True
NUMA_TRANSFER_PROC_LIST = ['SPECjbb', 'spark']
# 资源限制功能
RESOURCE_RESTRICT = True
RESTRICT_PROC_LIST = ['spark']
RESTRICT_PARAM = {'MB': 20}

WAAS_CODEPLOY_MANAGER = '/var/run/waas_codeploy/'
PID_FILE = '/var/run/waas_codeploy/waas_codeploy.pid'
LOG_PATH = '/var/log/waas_codeploy.log'
PID_INFO_FILE = '/var/run/waas_codeploy/waas_codeploy.json'
LOG_SAVE_PATH = '/var/log/'
LOG_LEVEL_INFO = 'INFO'
LOG_LEVEL_DEBUG = 'DEBUG'
LOG_LEVEL_ERROR = 'ERROR'
LOG_LEVEL_WARNING = 'WARNING'
LOG_LEVEL_CRITICAL = 'CRITICAL'
LOG_LEVEL_LIST = ['INFO', 'DEBUG', 'ERROR', 'WARNING', 'CRITICAL']
GLOBAL_LOG_LEVEL = 'INFO'
LOG_NUM = 20
LOG_SIZE = 50
QUERY = 'query'
PID = 'pid'
CPUSET = 'cpuset'
CPUACCT = 'cpuacct'
CGROUP = 'cgroups'
CONTAINER_ILLEGAL = 'container_id_illegal'
CPUSET_RAW = 'cgroup_cpuset_raw'
CPUSET_CPUS = 'cgroup_cpuset_cpus'
AFFINITY = 'process_affinity'
QUERIES = 'queries'
INFO = 'info'
WORK_INTERVAL = 30
MONITOR_DURATION = 1
BIND_CORE_NUM = 4
WAIT_INTERVAL = 1
PROC_LIST = ['SPECjbb']
EVT_LIST = [
    "l1d_tlb_refill", "l1d_tlb",
    "l1i_tlb_refill", "l1i_tlb",
    "l2d_tlb_refill", "l2d_tlb",
    "l2i_tlb_refill", "l2i_tlb"
]
OVERLOAD_METRIC = 'l2i' 
METRIC_INDEX = 'miss_rate'
OVERLOAD_THRE = 0.01


def set_affinity(tid_list, cpu_list):
    '''
    绑定进程/线程到指定CPU列表'''
    if not cpu_list:
        logging.warning("Cpu bind list is empty")
        return False
    elif not tid_list:
        logging.debug("Tid bind list is empty")
        return False
    for tid in tid_list:
        try:
            os.sched_setaffinity(tid, cpu_list)
            logging.info("Thread %s addinity updated to: %s", tid, cpu_list)
        except PermissionError:
            logging.warning("Permission denied when setting affinity for thread: %s", tid)
        except ProcessLookupError:
            logging.warning("Thread %s does not exist", tid)
        except Exception as e:
            logging.warning("Failed to set thread %s affinity for: %s", tid, e)

    return True


def get_threads_psutil(pid):
    '''
    获取进程的所有线程'''
    try:
        # 获取进程对象
        p = psutil.Process(int(pid))
        threads = p.threads()
        spids = [t.id for t in threads]
        
        return spids
        
    except psutil.NoSuchProcess:
        logging.warning("No such thread: %s", pid)
        return []
    except psutil.AccessDenied:
        logging.warning("Permission denied for thread: %s", pid)
        return []


def list_numeric_proc_dirs() -> List[str]:
    return [d for d in os.listdir('/proc') if d.isdigit()]


def read_file(path: str) -> Optional[str]:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return None


def get_proc_name_and_cmdline(pid: str) -> str:
    # 尝试 /proc/<pid>/comm -> 最准确, 然后 cmdline
    comm, cmd = f'pid:{pid}', f'pid:{pid}'
    comm = read_file(f'/proc/{pid}/comm')
    cmd = read_file(f'/proc/{pid}/cmdline')
    
    return comm, cmd


def find_pids_by_identifiers(idents: List[str]) -> Dict[str, List[int]]:
    """
    idents: 列表，元素可能为数字(pid)或字符串(进程名)
    返回 mapping: ident -> [pid,...]
    """
    found = {ident: [] for ident in idents}
    # 先把数字id直接检查一下
    for ident in idents:
        if ident.isdigit() and os.path.isdir(f'/proc/{int(ident)}'):
            pid = int(ident)
            found[ident].append(pid)
        elif not ident.isdigit():
            found = find_ident_in_proc(found, idents)
    return found


def find_ident_in_proc(found: dict, idents: List[str]) -> Dict[str, List[int]]:
    numeric_dirs = list_numeric_proc_dirs()
    for pid in numeric_dirs:
        pid_int = int(pid)
        name, cmd = get_proc_name_and_cmdline(pid)
        for ident in idents:
            # name 匹配逻辑：完全相等或 ident 在 cmdline 首项/comm 中出现
            if name and (ident == name or ident in name):
                found[ident].append(pid_int)
            elif cmd and ident in cmd:
                found[ident].append(pid_int)
    return found


def parse_proc_cgroup(pid: int) -> Dict[str, str]:
    """
    解析 /proc/<pid>/cgroup
    返回 mapping controller -> cgroup_path
    对于 cgroup v2 (single hierarchy) 返回 key 'cgroup2' -> path
    """
    data = read_file(f'/proc/{pid}/cgroup')
    if not data:
        return {}
    res = {}
    for line in data.splitlines():
        parts = line.strip().split(':', 2)
        if len(parts) == 3:
            subs, controllers, path = parts
            controllers = controllers.strip()
            path = path.strip()
            res[controllers] = path
    return res


def find_cpuset_mountpoint() -> Tuple[Optional[str], bool]:
    """
    返回 (mount_point, is_cgroup_v2)
    查 /proc/self/mounts 寻找 cpuset 的挂载点（优先找 v1 cpuset），否则找 cgroup2 root。
    """
    mounts = read_file('/proc/self/mounts') or ''
    cpuset_mount = None
    cgroup2_mount = None
    for line in mounts.splitlines():
        # 格式: device mountpoint fstype options ...
        parts = line.split()
        if len(parts) < 3:
            continue
        fstype = parts[2]
        mountpoint = parts[1]
        options = parts[3] if len(parts) > 3 else ''
        # cgroup v1 cpuset might be type "cgroup" and options contain "cpuset"
        if fstype == 'cgroup' and 'cpuset' in options.split(','):
            cpuset_mount = mountpoint
            break
        # also check explicit cpuset v1 robustness: some systems mount as cpuset fs type
        if fstype == 'cpuset':
            cpuset_mount = mountpoint
            break
        # cgroup v2
        if fstype == 'cgroup2' and cgroup2_mount is None:
            cgroup2_mount = mountpoint
    if cpuset_mount:
        return cpuset_mount, False
    if cgroup2_mount:
        return cgroup2_mount, True
    return None, False


def read_cpuset_from_cgroup(base_mount: str, cgroup_path: str) -> Optional[str]:
    """
    base_mount: cpuset controller mountpoint (or cgroup v2 mountpoint)
    cgroup_path: path from /proc/<pid>/cgroup (starts with /)
    尝试读取 cpuset.cpus 文件
    """
    if not base_mount:
        return None
    # unify path
    rel = cgroup_path.lstrip('/')
    candidate = os.path.join(base_mount, rel, 'cpuset.cpus')
    if os.path.isfile(candidate):
        return (read_file(candidate) or '').strip()
    # sometimes the cpuset controller uses different subdirs (try direct join)
    candidate2 = os.path.join(base_mount, 'cpuset.cpus')
    if os.path.isfile(candidate2):
        return (read_file(candidate2) or '').strip()
    # also try /sys/fs/cgroup/cpuset + rel (some distros)
    candidate3 = os.path.join('/sys/fs/cgroup/cpuset', rel, 'cpuset.cpus')
    if os.path.isfile(candidate3):
        return (read_file(candidate3) or '').strip()
    return None


def read_cpumem_from_cgroup(base_mount: str, cgroup_path: str) -> Optional[str]:
    rel = cgroup_path.lstrip('/')
    candidate = os.path.join(base_mount, rel, 'cpuset.mems')
    if os.path.isfile(candidate):
        return (read_file(candidate) or '').strip()
    return None


def parse_cpu_range_list(s: str) -> List[int]:
    """
    将 cpuset 表示 "0-3,5,7-8" -> [0,1,2,3,5,7,8]
    如果输入为空或 '': 返回空列表
    """
    if not s:
        return []
    s = s.strip()
    items = []
    for part in s.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a,b = part.split('-',1)
            try:
                a_i = int(a); b_i = int(b)
                if b_i >= a_i:
                    items.extend(range(a_i, b_i+1))
            except:
                continue
        else:
            try:
                items.append(int(part))
            except:
                continue
    # dedupe & sort
    return sorted(set(items))


def guess_container_id_from_cgroup_path(cg_path: str) -> Optional[str]:
    """
    根据常见 cgroup 路径
    支持：
      - /docker/<containerid>/...
      - /kubepods/.../pod<uuid>/<containerid>
      - /system.slice/docker-<containerid>.scope
      - /containerd/io.containerd.runtime.v2.task/<namespace>/<id>/...
    """
    if not cg_path:
        return False
    patterns = [
        r'docker',
        r'kubepods',
        r'containerd'
    ]
    return any(re.search(p, cg_path) for p in patterns)


def inspect_processes(idents: List[str], pid_map: dict) -> Dict:
    results = {
        QUERIES: idents,
        INFO: [],
    }
    logging.info("Target pid map is: %s", pid_map)
    base_mount, _ = find_cpuset_mountpoint()
    for ident, pids in pid_map.items():
        for pid in pids:
            proc_info = {
                QUERY: ident,
                PID: pid,
                CGROUP: {},
                CONTAINER_ILLEGAL: None,
                CPUSET_RAW: None,
                CPUSET_CPUS: [],
                AFFINITY: None,
                'notes': []
            }
            # cgroup
            cg = parse_proc_cgroup(pid)
            proc_info['cgroups'] = cg
            use_path = None
            if 'cpuset' in cg:
                use_path = cg['cpuset']
                proc_info[CONTAINER_ILLEGAL] = guess_container_id_from_cgroup_path(use_path)
                cpuset_raw = None
                if base_mount:
                    cpuset_raw = read_cpuset_from_cgroup(base_mount, use_path)
                if cpuset_raw is None:
                    proc_info['notes'].append('cpuset.cpus file not found via cgroup mountpoint; fallback to process affinity')
                else:
                    proc_info[CPUSET_RAW] = cpuset_raw
                    proc_info[CPUSET_CPUS] = parse_cpu_range_list(cpuset_raw)
            else:
                proc_info['notes'].append('no cgroup path discovered for this process')
            try:
                aff = os.sched_getaffinity(pid)
                proc_info[AFFINITY] = sorted(list(aff))
            except Exception as e:
                proc_info['notes'].append(f'failed to get process affinity: {e}')
            # logging.debug("ident: %s pid: %s proc_info is: %s", ident, pid, proc_info)
            if proc_info[CONTAINER_ILLEGAL]:
                results[INFO].append(proc_info)

    return results


def group_pids_by_cpuset(results: Dict) -> dict:
    """
    输入: pid_to_cpuset = {pid: ...}
    输出: { "48,...,95": [pid1, pid2, ...], ... } 仅包含有重复的范围
    """
    pid_to_cpuset = {}
    for pid_info in results[INFO]:
        pid_to_cpuset.update({pid_info.get(PID): pid_info.get(CPUSET_CPUS)})
    cpuset_to_pids = {}
    for pid, cpuset in pid_to_cpuset.items():
        cpuset_to_pids.setdefault(tuple(sorted(cpuset)), []).append(pid)

    return cpuset_to_pids


def calculate_pid_bind_core(cpuset_to_pids: dict) -> dict:
    pid_core_dict = {}
    for cpu_range, pid_list in cpuset_to_pids.items():
        cpu_list = get_physical_core(list(cpu_range))
        block_count = int(len(cpu_list) / BIND_CORE_NUM)
        for idx, pid in enumerate(sorted(pid_list)):
            # 循环分配块编号
            block_id = idx % block_count

            start = block_id * BIND_CORE_NUM
            end = start + BIND_CORE_NUM

            assigned = cpu_list[start:end]
            pid_core_dict.update({pid: assigned})

    return pid_core_dict


def get_physical_core(cpu_range: list) -> list:
    '''
    获取绑核范围内的物理核
    '''
    evens = [int(cpu) for cpu in cpu_range if cpu % 2 == 0]
    return evens


def set_cgroup_cpuset(base_mount, cgroup, cpu_info):
    cpuset = cpu_info[0]
    cpumem = cpu_info[1]
    if base_mount.endswith('/'):
        base_mount = base_mount[:-1]
    if cgroup.startswith('/'):
        cgroup = cgroup[1:]

    path = os.path.join(base_mount, cgroup, "cpuset.cpus")
    if not os.path.exists(path):
        logging.warning(f"Path not found: {path}")
        return False
    try:
        # 写入新的 CPU 列表
        with open(path, 'w') as f:
            f.write(cpuset)
            f.flush()
        
        # 同时需要更新 cpuset.mems 以确保内存亲和性（通常必须与 cpuset.cpus 匹配）
        mems_path = os.path.join(base_mount, cgroup, "cpuset.mems")
        if os.path.exists(mems_path):
            with open(mems_path, 'w') as f:
                f.write(str(cpumem))
        return True
    except Exception as e:
        logging.warning(f"Failed to set cgroup cpuset: {e}")
        return False


if __name__ == '__main__':
    target_process_list = ['SPECjbb']
    pid_map = find_pids_by_identifiers(target_process_list)
    results = inspect_processes(target_process_list, pid_map)
    print(results)
    cpuset_to_pids = group_pids_by_cpuset(results)
    print(cpuset_to_pids)
    pid_core_dict = calculate_pid_bind_core(cpuset_to_pids)
    print(pid_core_dict)
    for pid, cpu_list in pid_core_dict.items():
        spid = get_threads_psutil(pid)
        print(set_affinity(spid, cpu_list))