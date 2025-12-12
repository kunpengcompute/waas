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

import waas_log as logging


class ResctrlManager:
    def __init__(self, update_param, resctrl_root="/sys/fs/resctrl"):
        self.resctrl_root = resctrl_root
        # 检查 resctrl 是否挂载
        if not os.path.ismount(self.resctrl_root):
            logging.warning(f"{self.resctrl_root} is not mounted. "
                  "Please ensure MPAM is enabled and mounted.")
        self.update_param = update_param

    def process_containers(self, cgroup_paths):
        """
        批量处理容器路径列表
        :param cgroup_paths: list, 例如 ['/sys/fs/cgroup/cpuset/system.slice/docker-xxxxx']
        """
        for cgroup_path in cgroup_paths:
            self._process_single_container(cgroup_path)

    def _process_single_container(self, cgroup_path):
        # 0. 基础校验与名称提取
        if not os.path.exists(cgroup_path):
            logging.warning(f"Cgroup path does not exist: {cgroup_path}")
            return

        # 提取 docker-xxxxx，通常是路径的最后一部分
        # 如果路径以 / 结尾，basename 可能为空，需要处理
        clean_path = cgroup_path.rstrip('/')
        dir_name = os.path.basename(clean_path)
        
        # 目标 resctrl 目录路径
        resctrl_group_path = os.path.join(self.resctrl_root, dir_name)

        try:
            # 1. 创建 resctrl 目录
            if not os.path.exists(resctrl_group_path):
                os.mkdir(resctrl_group_path)
                logging.info(f"Resctrl group Created: {resctrl_group_path}")
            else:
                logging.info(f"Resctrl group already exists: {resctrl_group_path}")

            # 2. 迁移 tasks (PIDs)
            self._migrate_tasks(cgroup_path, resctrl_group_path)

            # 3. 修改 schemata
            self._update_schemata(resctrl_group_path)

        except PermissionError:
            logging.warning("[Error] Permission denied. Please run as root.")
        except Exception as e:
            logging.warning(f"Failed to process {dir_name}: {e}")

    def _migrate_tasks(self, src_cgroup_path, dst_resctrl_path):
        """
        读取源 cgroup 的 tasks 并写入目标 resctrl 的 tasks
        """
        src_tasks_file = os.path.join(src_cgroup_path, 'tasks')
        dst_tasks_file = os.path.join(dst_resctrl_path, 'tasks')

        if not os.path.exists(src_tasks_file):
            logging.warning(f"Source tasks file not found: {src_tasks_file}")
            return

        try:
            # 读取所有 PID
            with open(src_tasks_file, 'r') as f:
                pids = f.read().split()

            if not pids:
                logging.info(f"No tasks found in {src_cgroup_path}")
                return

            # 写入 PID (sysfs 要求一次写入一个 PID)
            count = 0
            for pid in pids:
                try:
                    with open(dst_tasks_file, 'w') as f:
                        f.write(pid)
                    count += 1
                except ProcessLookupError:
                    # 进程可能在读取后已经结束，忽略此错误
                    continue
                except OSError as e:
                    # 某些内核线程无法移动，或者进程已死
                    logging.debug(f"Could not move PID {pid}: {e}")
                    continue
            
        except Exception as e:
            logging.error(f"Task migration failed: {e}")

    def _update_schemata(self, resctrl_group_path):
        """
        修改 schemata 文件中的 MB 配置
        """
        schemata_path = os.path.join(resctrl_group_path, 'schemata')
        
        if not os.path.exists(schemata_path):
            logging.error(f"Schemata file not found: {schemata_path}")
            return

        try:
            # 读取当前配置
            with open(schemata_path, 'r') as f:
                lines = f.readlines()

            new_content = ""
            mb_modified = False

            for line in lines:
                line = line.strip()
                if line.startswith("MB:"):
                    # 解析 MB 行，例如: MB:0=100;1=100;2=100
                    try:
                        prefix, values = line.split(':', 1)
                        # 分割各个节点的配置 (0=100, 1=100)
                        node_configs = values.split(';')
                        
                        new_node_configs = []
                        for config in node_configs:
                            if '=' in config:
                                node_id, _ = config.split('=')
                                # 核心逻辑：强制设置为 20
                                new_node_configs.append(f"{node_id}={self.update_param}")
                        
                        # 重组行
                        new_line = f"MB:{';'.join(new_node_configs)}\n"
                        new_content += new_line
                        mb_modified = True
                        logging.info(f"Changing schemata MB from '{line}' to '{new_line.strip()}'")
                    except Exception as parse_e:
                        logging.error(f"Failed to parse MB line '{line}': {parse_e}")
                        new_content += line + "\n" # 保持原样防止破坏文件
                else:
                    new_content += line + "\n"

            # 写入修改后的配置
            if mb_modified:
                with open(schemata_path, 'w') as f:
                    f.write(new_content)
                    f.flush()
                logging.info("Schemata %s updated.", schemata_path)
            else:
                logging.info("No MB configuration found in schemata to update.")

        except Exception as e:
            logging.error(f"Failed to update schemata: {e}")

# --- 使用示例 ---
if __name__ == "__main__":
    # 模拟输入列表
    # 请确保这些路径在你的机器上是真实存在的，否则脚本会报错
    cgroup_list = [
        '/sys/fs/cgroup/cpuset/system.slice/docker-testcontainer1'
    ]

    manager = ResctrlManager()
    manager.process_containers(cgroup_list)

