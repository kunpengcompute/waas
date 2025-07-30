# -*- coding: utf-8 -*-

import subprocess
import boost_log as logging
from util import get_container_info, OG_QUOTA, AC_QUOTA, BT_QUOTA, CPU_SHARES


def _get_cgroup_version():
    try:
        result = subprocess.run(
            ['stat', '-fc', '%T', '/sys/fs/cgroup'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return "error"
        fs = result.stdout.strip()

        if fs == "tmpfs":
            return "v1"
        elif fs == "cgroup2fs":
            return "v2"
        else:
            return fs

    except FileNotFoundError as fe:
        raise FileNotFoundError(f"get cgroup version file error, {fe}") from fe
    except PermissionError as pe:
        raise PermissionError(f"get cgroup version permission error, {pe}") from pe
    except Exception as e:
        raise Exception(f"get cgroup version error, {e}") from e


def _get_pods_to_limit(throttle_numa_nodes:dict, pod_quotas:dict, pod_numa_nodes:dict):
    overwhelm_pods = {}
    for pod_path, pod_info in pod_quotas.items():
        if pod_info.get(AC_QUOTA) <= pod_info.get(BT_QUOTA):
            continue
        if 'all' in throttle_numa_nodes.keys():
            overwhelm_pods.update({pod_path: pod_info})
        else:
            for node in pod_numa_nodes.get(pod_path):
                if node in throttle_numa_nodes.keys():
                    overwhelm_pods.update({pod_path: pod_info})
                    break
    return overwhelm_pods


def _get_pods_to_scale(throttle_numa_nodes:dict, pod_quotas:dict, pod_numa_nodes:dict):
    scalable_pods = {}
    for pod_path, pod_info in pod_quotas.items():
        scalable = True
        for node in pod_numa_nodes.get(pod_path):
            if node in throttle_numa_nodes.keys():
                scalable = False
                break
        if scalable:
            scalable_pods.update({pod_path: pod_info})
    return scalable_pods


def _get_overload_pods(pod_path, pod_quotas, pod_dict):
    if pod_path in pod_quotas.keys():
        pod_info = pod_quotas.get(pod_path)
        if pod_info.get(AC_QUOTA) > pod_info.get(BT_QUOTA):
            pod_dict.update({pod_path: pod_info})
    return pod_dict


class QuotaManager:
    def __init__(self):
        self.total_quota = 0
        self.overload_threshold_v1 = 0.8
        self.overload_threshold_v2 = 0.9
        self.balance_ratio = 0.8

        self.cgroup_version = _get_cgroup_version()
        if self.cgroup_version == 'v1':
            self.period_path = "/sys/fs/cgroup/cpu/cpu.cfs_period_us"
        elif self.cgroup_version == 'v2':
            self.period_path = None # 暂不支持
        else:
            self.period_path = None
            raise Exception(f"unknown file system {self.cgroup_version}")
            
    
    def quota_approval(self, pod_quotas:dict, boosted_pods:dict, numa_cpu_utils:dict, pod_numa_nodes:dict, pod_forecast:dict):
        try:
            throttle_nodes = self._check_numa_util(numa_cpu_utils)
            if not throttle_nodes:
                return pod_quotas
            elif 'all' in throttle_nodes.keys():
                if not boosted_pods:
                    return _get_pods_to_limit(throttle_nodes, pod_quotas, pod_numa_nodes)
                balanced_pods = self._balance_pods(pod_quotas, boosted_pods, pod_numa_nodes, 'all')
                logging.info('Host cpu overwhelm, balanced pos: %s', balanced_pods)
                return balanced_pods
            else:
                pods_to_scale = _get_pods_to_scale(throttle_nodes, pod_quotas, pod_numa_nodes)
                if not boosted_pods:
                    pods_to_limit = _get_pods_to_limit(throttle_nodes, pod_quotas, pod_numa_nodes)
                    return {**pods_to_scale, **pods_to_limit}
                logging.debug('boosted pods: %s', boosted_pods)

                pods_to_balanced = self._get_pods_to_balance(throttle_nodes, boosted_pods, pod_numa_nodes)
                logging.debug('pods to balance: %s', pods_to_balanced)
                balanced_pods = self._balance_pods(pod_quotas, pods_to_balanced, pod_numa_nodes, 'numa')
                logging.info('overhead numa node: %s, balanced pods: %s', throttle_nodes, balanced_pods)
                output = {**pods_to_scale, **balanced_pods}
                return output

        except Exception as e:
            logging.warning('Quota approval faild, error:%s', e)
            return {}


    def _check_numa_util(self, numa_cpu_utils):
        throttle_nodes = {}
        if not numa_cpu_utils:
            return throttle_nodes
        for node, node_utils in numa_cpu_utils.items():
            if not node_utils:
                avg_util = 0
            else:
                avg_util = sum(node_utils) / len(node_utils)
            if avg_util > self.overload_threshold_v2 * 100:
                throttle_nodes.update({node: avg_util})
        return throttle_nodes

    
    def _get_pods_to_balance(self, throttle_nodes, boosted_pods, pod_numa_nodes):
        pods_to_balance = {}
        if not throttle_nodes:
            return pods_to_balance
        if 'all' in throttle_nodes.keys():
            pods_to_balance = boosted_pods
            return pods_to_balance

        for node in throttle_nodes.keys():
            for pod_path, pod_node in pod_numa_nodes.items():
                if node in pod_node:
                    pod_info = boosted_pods.get(pod_path)
                    pods_to_balance.update({pod_path: pod_info})
        return pods_to_balance


    def _balance_pods_by_share(self, pod_shares, total_boost_quota, boosted_pods, pod_quotas, balanced_pod):
        pod_priority = {key: 10000 / value for key, value in pod_shares.items()}
        total_pod_priority = sum(pod_priority.values())
        logging.debug('pod priority: %s', pod_priority)

        for pod_path, pod_ratio in pod_priority.items():
            if total_pod_priority != 0:
                delta_quota = int(pod_ratio / total_pod_priority * total_boost_quota * (1 - self.balance_ratio))
            else:
                delta_quota = 0
            pod_info = boosted_pods.get(pod_path)
            if pod_info.get(BT_QUOTA) - delta_quota >= pod_info.get(OG_QUOTA):
                quota_adjust = pod_info.get(BT_QUOTA) - delta_quota
            else:
                quota_adjust = pod_info.get(OG_QUOTA)

            if pod_path in pod_quotas.keys() and quota_adjust > pod_quotas.get(pod_path).get(BT_QUOTA):
                balanced_pod.update({pod_path: pod_quotas.get(pod_path)})
            else:
                balanced_pod.update({pod_path: {
                    AC_QUOTA: boosted_pods.get(pod_path).get(BT_QUOTA),
                    BT_QUOTA: quota_adjust
                }})


    def _balance_pods(self, pod_quotas, pods_to_balanced, pod_nodes, mode):
        balanced_pod = {}
        pod_priority = {}
        pod_shares = {}
        boosted_pods = {}
        total_boost_quota = 0
        if mode != "all" and mode != "numa":
            return {}
        for pod_path, pod_info in pods_to_balanced.items():
            if not pod_info:
                continue
            if pod_info.get(OG_QUOTA) < pod_info.get(BT_QUOTA):
                boosted_pods.update({pod_path: pod_info})
                total_boost_quota += pod_info.get(BT_QUOTA) - pod_info.get(OG_QUOTA)
                if mode == "all":
                    pod_shares.update({pod_path: int(get_container_info(pod_path, CPU_SHARES))})
                elif mode == 'numa':
                    pod_shares.update({pod_path: \
                        int(get_container_info(pod_path, CPU_SHARES)) / len(pod_nodes.get(pod_path))})
                else:
                    raise Exception(f"unknown mode:{mode} to balance pods")
            else:
                balanced_pod = _get_overload_pods(pod_path, pod_quotas, balanced_pod)

        if not pod_shares:
            return balanced_pod

        self._balance_pods_by_share(pod_shares, total_boost_quota, boosted_pods, pod_quotas, balanced_pod)
        return balanced_pod