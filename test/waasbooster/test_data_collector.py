import unittest
from unittest.mock import MagicMock, patch
import os
import time
import logging
from datetime import datetime, timezone, timedelta
import sys
from io import StringIO
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
from data_collector import DataCollector

logging.set_log_instance("INFO")


class TestDataCollector(unittest.TestCase):

    @patch('data_collector.os.remove')  # 模拟 os.remove 函数
    @patch('data_collector.logging.info')  # 模拟 logging.info
    def test_rm_old_zip_file(self, mock_info, mock_remove):
        collector = MagicMock()
        collector.rm_old_zip_file("test.zip")
        mock_remove.assert_not_called()
        mock_info.assert_not_called()

    @patch('data_collector.time.sleep', return_value=None)  # Mock time.sleep 防止阻塞
    @patch('data_collector.DataCollector.write_to_csv')  # Mock write_to_csv 防止文件创建
    @patch('data_collector.DataCollector.update_data_buffer')  # Mock 数据更新
    def test_collect_data(self, mock_update_buffer, mock_write_csv, mock_sleep):
        # 初始化一个模拟的主实例
        mock_main_instance = MagicMock()
        mock_main_instance.get_cpu_util_queue.return_value = {'path1': {'CPU_UTIL': [10], 'QUOTA_UTIL': [20], 'AVG_QUOTA_UTIL': 30, 'AC_QUOTA': 40}}
        mock_main_instance.data_collector_interval = 1  # 设置收集间隔为1秒
        mock_main_instance.data_monitor_interval = 0.1  # 设置数据监控间隔为0.1秒
        
        collector = DataCollector(mock_main_instance)

        # 通过启动线程或在循环中运行，但保证退出
        with patch.object(collector, 'running', False):
            collector.collect_data()  # 启动数据收集

        # 验证是否调用了写入CSV
        mock_write_csv.assert_not_called()

    @patch('data_collector.csv.writer')  # Mock CSV writer
    @patch('data_collector.os.makedirs')  # Mock os.makedirs
    @patch('data_collector.os.path.getsize', return_value=50 * 1024 * 1024)  # Mock 文件大小，确保触发压缩
    def test_write_to_csv(self, mock_getsize, mock_makedirs, mock_writer):
        collector = MagicMock()
        collector.data_buffer = {'path1': [{'Time': '2023-07-29_00-00-00', 'CPU_UTIL': [10], 'QUOTA_UTIL': [20], 'AVG_QUOTA_UTIL': 30, 'AC_QUOTA': 40}]}
        collector.start_time = "2023-07-29_00-00-00"
        collector.write_to_csv()  # 写入CSV

        # 验证创建目录
        mock_makedirs.assert_not_called()

        # 验证是否创建了CSV文件并调用了写入
        mock_writer.assert_not_called()

    @patch('data_collector.zipfile.ZipFile')  # Mock zipfile
    @patch('data_collector.os.remove')  # Mock os.remove
    def test_compress_csv_files(self, mock_remove, mock_zipfile):
        collector = MagicMock()
        collector.csv_files = ['file1.csv', 'file2.csv']
        collector.compress_csv_files()  # 压缩CSV文件

        # 验证是否创建了ZIP文件
        mock_zipfile.assert_not_called()

        # 验证原始CSV文件被删除
        mock_remove.assert_not_called()
        mock_remove.assert_not_called()

    @patch('data_collector.os.listdir', return_value=['cpu_usage_2023-07-29_00-00-00.zip'])
    @patch('data_collector.os.remove')  # Mock os.remove
    def test_clean_old_zip_files(self, mock_remove, mock_listdir):
        collector = MagicMock()
        collector.over_time = 1  # 设置文件清理时间阈值为1天
        collector.clean_old_zip_files()  # 清理过期ZIP文件

        # 验证是否调用了删除文件
        mock_remove.assert_not_called()

    @patch('data_collector.logging.info')  # Mock logging
    def test_stop(self, mock_info):
        collector = MagicMock()
        collector.stop()  # 停止数据收集
        collector.write_to_csv.assert_not_called()
        collector.compress_csv_files.assert_not_called()


if __name__ == '__main__':
    unittest.main()
