# -*- coding: utf-8 -*-
# 版权所有 (c) 华为技术有限公司 2025-2025


import unittest
from unittest.mock import patch, mock_open
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
from quota_updater import quota_updater, _update_parent_quota  

logging.set_log_instance("INFO")

class TestQuotaUpdater(unittest.TestCase):
    
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_quota_updater_success(self, mock_open_func, mock_exists):
        cgroup_path = "/sys/fs/cgroup/pod1"
        quota_value = 100000
        quota_path = os.path.join(cgroup_path, "cpu.cfs_quota_us")
        parent_cgroup_path = os.path.join(os.path.dirname(cgroup_path), "cpu.cfs_quota_us")
        
        # Mock os.path.exists return values
        mock_exists.side_effect = lambda x: x in [quota_path, parent_cgroup_path]

        # Mock the contents of the files
        mock_open_func.return_value.read.return_value = '100000'
        
        # Patch logging to check if it's called correctly
        with patch.object(logging, 'info') as mock_info, patch.object(logging, 'error') as mock_error:
            result = quota_updater(cgroup_path, quota_value)
        
            # Assert the result is True (success)
            self.assertTrue(result)
            
            # Check if the expected log calls were made
            mock_info.assert_called_with('Update pod: %s, quota: %s', cgroup_path, quota_value)
            mock_error.assert_not_called()
            
            # Check if the file was opened with correct values
            mock_open_func.assert_any_call(quota_path, 'w')
            mock_open_func.assert_any_call(quota_path, 'r')


    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_quota_updater_parent_quota_not_updated(self, mock_open_func, mock_exists):
        cgroup_path = "/sys/fs/cgroup/pod1"
        quota_value = 100000
        quota_path = os.path.join(cgroup_path, "cpu.cfs_quota_us")
        parent_cgroup_path = os.path.join(os.path.dirname(cgroup_path), "cpu.cfs_quota_us")
        
        # Mock os.path.exists return values
        mock_exists.side_effect = lambda x: x in [quota_path, parent_cgroup_path]

        # Mock the contents of the files
        mock_open_func.return_value.read.return_value = '200000'
        
        # Patch logging to check if it's called correctly
        with patch.object(logging, 'info') as mock_info, patch.object(logging, 'error') as mock_error:
            result = quota_updater(cgroup_path, quota_value)
        
            # Assert the result is False (failure)
            self.assertFalse(result)
            
            # Check if the expected log calls were made
            mock_info.assert_not_called()
            mock_error.assert_called_with(
                "Failed to update pod %s quota to %d, actual: %d",
                cgroup_path,
                quota_value,
                200000
            )


    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_quota_updater_no_quota_file(self, mock_open_func, mock_exists):
        cgroup_path = "/sys/fs/cgroup/pod1"
        quota_value = 100000
        quota_path = os.path.join(cgroup_path, "cpu.cfs_quota_us")
        
        # Mock os.path.exists return value to simulate no quota file
        mock_exists.side_effect = lambda x: x != quota_path
        
        with patch.object(logging, 'info') as mock_info, patch.object(logging, 'error') as mock_error:
            result = quota_updater(cgroup_path, quota_value)
        
            # Assert the result is False (failure)
            self.assertFalse(result)
            
            # Check if the expected log calls were made
            mock_info.assert_not_called()
            

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_quota_updater_exception(self, mock_open_func, mock_exists):
        cgroup_path = "/sys/fs/cgroup/pod1"
        quota_value = 100000
        quota_path = os.path.join(cgroup_path, "cpu.cfs_quota_us")
        error = Exception("File system error")
        # Mock os.path.exists return value to simulate quota file existence
        mock_exists.side_effect = lambda x: x == quota_path

        # Force an exception when opening the file
        mock_open_func.side_effect = error
        
        with patch.object(logging, 'info') as mock_info, patch.object(logging, 'error') as mock_error:
            result = quota_updater(cgroup_path, quota_value)
        
            # Assert the result is False (failure)
            self.assertFalse(result)
            
            # Check if the expected log calls were made
            mock_info.assert_not_called()
            mock_error.assert_not_called()


class TestUpdateParentQuota(unittest.TestCase):

    @patch("os.path.exists")
    def test_parent_cgroup_path_not_exist(self, mock_exists):
        # 模拟文件路径不存在
        parent_cgroup_path = "/sys/fs/cgroup/parent/cpu.cfs_quota_us"
        mock_exists.return_value = False
        
        result = _update_parent_quota(parent_cgroup_path, 100000)
        
        # 文件不存在，应该返回 False
        self.assertFalse(result)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_parent_quota_value_geq(self, mock_open_func, mock_exists):
        # 模拟文件路径存在，且配额值 >= quota_value
        parent_cgroup_path = "/sys/fs/cgroup/parent/cpu.cfs_quota_us"
        mock_exists.return_value = True
        
        # 模拟文件内容为 100000
        mock_open_func.return_value.read.return_value = '100000'
        
        result = _update_parent_quota(parent_cgroup_path, 100000)
        
        # 配额值 >= quota_value，应该返回 False
        self.assertFalse(result)
        
        # 检查文件未被写入
        mock_open_func.assert_called_once_with(parent_cgroup_path, 'r')
        mock_open_func.return_value.write.assert_not_called()


    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_parent_quota_value_updated(self, mock_open_func, mock_exists):
        # 模拟文件路径存在，且配额值 < quota_value
        parent_cgroup_path = "/sys/fs/cgroup/parent/cpu.cfs_quota_us"
        mock_exists.return_value = True
        
        # 模拟文件内容为 50000
        mock_open_func.return_value.read.return_value = '50000'
        
        result = _update_parent_quota(parent_cgroup_path, 100000)
        
        # 配额值被更新，应该返回 True
        self.assertTrue(result)
        
        # 检查文件被正确写入新的配额值
        mock_open_func.assert_any_call(parent_cgroup_path, 'w')
        mock_open_func.return_value.write.assert_called_with('100000')


    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_parent_quota_file_read_error(self, mock_open_func, mock_exists):
        # 模拟文件路径存在，但是读取文件时抛出异常
        parent_cgroup_path = "/sys/fs/cgroup/parent/cpu.cfs_quota_us"
        mock_exists.return_value = True
        
        # 模拟读取文件时抛出异常
        error = Exception("File read error")
        mock_open_func.side_effect = error
        try:
            result = _update_parent_quota(parent_cgroup_path, 100000)
        except Exception as e:
            self.assertEqual(e, error)
        


if __name__ == "__main__":
    unittest.main()
