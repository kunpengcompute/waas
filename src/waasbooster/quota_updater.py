# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025

import os
import boost_log as logging


def _update_parent_quota(parent_cgroup_path:str, quota_value:int):
    if not os.path.exists(parent_cgroup_path):
        return False
    with open(parent_cgroup_path, 'r') as q:
        parent_quota_value = int(q.read().strip())
        if parent_quota_value == -1 or parent_quota_value >= quota_value:
            return False
        else:
            with open(parent_cgroup_path, 'w') as q:
                q.write(str(quota_value))
            return True


def quota_updater(cgroup_path:str, quota):
    quota_value = int(quota)
    quota_path = os.path.join(cgroup_path, "cpu.cfs_quota_us")
    if not os.path.exists(quota_path):
        return False

    try:
        parent_quota_path = os.path.join(os.path.dirname(cgroup_path), "cpu.cfs_quota_us")
        _ = _update_parent_quota(parent_quota_path, quota_value)
        with open(quota_path, 'w') as q:
            q.write(str(quota_value))
        with open(quota_path, 'r') as q:
            new_quota_value = int(q.read().strip())
        if new_quota_value != quota_value:
            logging.error("Failed to update pod %s quota to %d, actual: %d", cgroup_path, quota_value, new_quota_value)
            return False
    except Exception as e:
        logging.error("Failed to update pod %s quota to %d, error: %s", cgroup_path, quota_value, e)
        return False
    logging.info('Update pod: %s, quota: %s', cgroup_path, quota)
    return True
