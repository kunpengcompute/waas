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

from datetime import datetime, timezone, timedelta
import time
import os
import csv
import logging
import zipfile
import util
from util import CPU_UTIL, QUOTA_UTIL, AVG_QUOTA_UTIL, AC_QUOTA


class DataCollector:
    def __init__(self, main_instance):
        self.main_instance = main_instance
        self.interval = main_instance.data_collector_interval   # 数据收集间隔
        self.running = True
        self.data_interval = main_instance.data_monitor_interval
        self.data_buffer = {} 
        self.start_time_raw = datetime.now(tz=timezone.utc) + timedelta(hours=8)
        self.start_time = self.start_time_raw.strftime("%Y-%m-%d_%H-%M-%S")
        self.last_write_time = datetime.now(tz=timezone.utc)
        self.csv_files = []         # 存储CSV文件路径
        self.total_csv_size = 0     # 用于跟踪CSV文件总大小
        self.zip_size = 100 * 1024 * 1024   # 压缩阈值100MB
        self.over_time = 30         # 数据超期清理天数

    @staticmethod
    def rm_old_zip_file(file_path):
        try:
            os.remove(file_path)
            logging.info('Remove old ZIP file: %s', file_path)
        except Exception as e:
            logging.error('Failed to remove old ZIP file %s for: %s', file_path, e)
    
    def collect_data(self):
        logging.info('Start to collect data')
        while self.running:
            try:
                cpu_queue_dict = self.main_instance.get_cpu_util_queue()
                current_time = datetime.now(tz=timezone.utc)
                formatted_time = current_time.strftime("%Y-%m-%d_%H-%M-%S")

                self.data_buffer = self.update_data_buffer(cpu_queue_dict, formatted_time)

                time_diff = (current_time - self.last_write_time).total_seconds()
                # 每隔一段数据写入CSV
                if time_diff >= self.interval:
                    self.write_to_csv()
                    self.last_write_time = current_time
                    # 清空缓冲区
                    self.data_buffer = {}

            except Exception as e:
                logging.warning('Data collection error: %s', e)
            time.sleep(self.data_interval)

    def update_data_buffer(self, cpu_queue_dict, current_time):
        for path, info in cpu_queue_dict.items():
            if path not in self.data_buffer:
                self.data_buffer[path] = []
            
            self.data_buffer[path].append({
                'Time': current_time,
                CPU_UTIL: list(info[CPU_UTIL]),
                QUOTA_UTIL: list(info[QUOTA_UTIL]),
                AVG_QUOTA_UTIL: info[AVG_QUOTA_UTIL],
                AC_QUOTA: info[AC_QUOTA]
            })
        
        return self.data_buffer

    def write_to_csv(self):
        end_time_raw = datetime.now(tz=timezone.utc) + timedelta(hours=8)
        end_time = end_time_raw.strftime("%Y-%m-%d_%H-%M-%S")
        save_dir = util.DATA_PATH
        os.makedirs(save_dir, exist_ok=True)
        filename = os.path.join(save_dir, f"cpu_usage_{self.start_time}_to_{end_time}.csv")

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # 写入表头
            writer.writerow(['Time', 'CPU_UTIL', 'QUOTA_UTIL', 'ACG_QUOTA_UTIL', 'AC_QUOTA', 'Path'])
            
            for path, data in self.data_buffer.items():
                for item in data:
                    # 将列表转为逗号分隔的字符串
                    cpu_util_str = ','.join(map(str, item[CPU_UTIL]))
                    quota_util_str = ','.join(map(str, item[QUOTA_UTIL]))
                    row = [
                        item['Time'],
                        cpu_util_str,
                        quota_util_str,
                        item[AVG_QUOTA_UTIL],
                        item[AC_QUOTA],
                        path
                    ]
                    writer.writerow(row)
        
        # 更新CSV文件跟踪信息
        file_size = os.path.getsize(filename)
        self.total_csv_size += file_size
        self.csv_files.append(filename)

        # 压缩CSV文件
        if self.total_csv_size >= self.zip_size:
            self.compress_csv_files()
            self.csv_files = []
            self.total_csv_size = 0

        self.start_time = end_time
        logging.debug('Data saved to %s', filename)

    
    def compress_csv_files(self):
        """压缩CSV文件"""
        if not self.csv_files:
            return 
        
        current_time = datetime.now(tz=timezone.utc) + timedelta(hours=8)
        zip_filename = os.path.join(util.DATA_PATH, f"cpu_usage_{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.zip")

        try:
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in self.csv_files:
                    zipf.write(file, os.path.basename(file))
            # 删除原始CSV文件
            for file in self.csv_files:
                os.remove(file)
            logging.info('Compressed CSV file into %s', zip_filename)

            # 清理过期ZIP文件
            self.clean_old_zip_files()

        except Exception as e:
            logging.error('Failed to compress CSV files for: %s', e)

    def clean_old_zip_files(self):
        """清理超期ZIP文件"""
        save_dir = util.DATA_PATH
        current_time = datetime.now(tz=timezone.utc) + timedelta(hours=8)

        for filename in os.listdir(save_dir):
            if filename.endswith('.zip'):
                # 提取时间戳
                parts = filename.split('_')
                if len(parts) < 4:
                    continue
                try:
                    # 文件名格式为cpu_usage_YYYY-MM-DD_HH-MM-SS.zip
                    timestamp_str = '_'.join(parts[2:]).split('.')[0]
                    file_time = datetime.strftime(timestamp_str, '%Y-%m-%d_%H-%M-%S').replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                # 计算时间差
                time_diff = current_time - file_time
                if time_diff.days > self.over_time:
                    file_path = os.path.join(save_dir, filename)
                    self.rm_old_zip_file(file_path)
    
    def stop(self):
        self.running = False
        self.write_to_csv()     # 保存剩余数据
        self.compress_csv_files()    # 压缩剩余CSV文件
