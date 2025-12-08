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

import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys
import time
from collections import deque
import pandas as pd
import numpy as np
from prophet import Prophet
from datetime import datetime, timedelta
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
from load_predictor import train_until_converged, get_forecast_load, data_pre, mean_squared_error


class TestDataPre(unittest.TestCase):

    def setUp(self):
        # 在测试前准备必要的测试数据
        self.load_data_valid = {
            "pod1": {
                "half_hour_avg": [
                    [i, datetime(2023, 7, 29, 0, 0) + timedelta(minutes=30*i), 20 + i] for i in range(100)
                ]
            }
        }
        
        self.load_data_invalid = {
            "pod1": {
                "half_hour_avg": [
                    [i, datetime(2023, 7, 29, 0, 0) + timedelta(minutes=30*i), None] for i in range(100)
                ]
            }
        }
        
        self.load_data_empty = {}
    
    def test_data_pre_valid(self):
        """测试数据足够且合格的情况"""
        data_qualified, pod_data = data_pre(self.load_data_valid)
        self.assertTrue(data_qualified)
        self.assertEqual(len(pod_data), 1)
        self.assertTrue('pod1' in pod_data)
        self.assertEqual(len(pod_data['pod1']), 96)  # 确保返回的数据长度为48

    def test_data_pre_invalid(self):
        """测试数据不合格的情况"""
        data_qualified, pod_data = data_pre(self.load_data_invalid)
        self.assertFalse(data_qualified)
        self.assertEqual(pod_data, {'pod1': None})

    def test_data_pre_empty(self):
        """测试数据为空的情况"""
        data_qualified, pod_data = data_pre(self.load_data_empty)
        self.assertFalse(data_qualified)
        self.assertEqual(pod_data, {})

    def test_data_pre_partial_valid(self):
        """测试部分数据有效的情况"""
        load_data_partial = {
            "pod1": {
                "half_hour_avg": [
                    [i, datetime(2023, 7, 29, 0, 0) + timedelta(minutes=30*i), 20 + i] for i in range(30)
                ]
            }
        }
        data_qualified, pod_data = data_pre(load_data_partial)
        self.assertFalse(data_qualified)
        self.assertEqual(pod_data, {'pod1': None})

    def test_data_pre_multiple_pods(self):
        """测试多个Pod的情况"""
        load_data_multiple_pods = {
            "pod1": {
                "half_hour_avg": [
                    [i, datetime(2023, 7, 29, 0, 0) + timedelta(minutes=30*i), 20 + i] for i in range(100)
                ]
            },
            "pod2": {
                "half_hour_avg": [
                    [i, datetime(2023, 7, 29, 0, 0) + timedelta(minutes=30*i), 25 + i] for i in range(50)
                ]
            }
        }
        data_qualified, pod_data = data_pre(load_data_multiple_pods)
        self.assertTrue(data_qualified)
        self.assertEqual(len(pod_data), 2)  # 只返回合格的数据
        self.assertTrue('pod1' in pod_data)
        self.assertTrue('pod2' in pod_data)


class TestTrainUntilConverged(unittest.TestCase):

    def setUp(self):
        """在每个测试前初始化数据和模拟模型"""
        # 创建一个简单的DataFrame作为测试数据
        time_index = pd.date_range(start='2023-01-01', periods=100, freq='30min')

        # 生成正弦波数据（模拟周期性数据）
        # 使用 np.sin 生成一个周期性的正弦波，振幅范围在 [-1, 1] 之间
        amplitude = 10  # 振幅
        period = 48  # 48个半小时为一个周期
        frequency = 2 * np.pi / period  # 计算每个半小时的频率，使得周期为48个半小时

        # 生成目标值
        y_values = amplitude * np.sin(frequency * np.arange(100))  # 生成正弦波

        # 创建 DataFrame
        self.df = pd.DataFrame({
            'ds': time_index,   # 时间戳
            'y': y_values       # 正弦波值作为目标值
        })
        
        # 创建一个预期的 Prophet 模型
        self.mock_model = MagicMock(spec=Prophet)
        
        # 模拟 Prophet 的方法
        self.mock_model.fit.return_value = None
        self.mock_model.make_future_dataframe.return_value = self.df
        self.mock_model.predict.return_value = self.df
        self.mock_model.add_seasonality.return_value = None

    @patch('load_predictor.Prophet', return_value=MagicMock(spec=Prophet))
    def test_train_until_converged_cross_validation(self, MockProphet):
        """测试交叉验证模式下，train_until_converged 函数的行为"""
        
        # 模拟 Prophet 返回的模型
        mock_prophet_instance = MockProphet.return_value
        
        # 模拟交叉验证过程
        mock_prophet_instance.fit.return_value = None
        mock_prophet_instance.predict.return_value = self.df
        mock_prophet_instance.add_seasonality.return_value = None
        mock_prophet_instance.make_future_dataframe.return_value = self.df
        
        # 返回固定的 RMSE
        with patch('load_predictor.cross_validation') as mock_cv, patch('load_predictor.performance_metrics') as mock_metrics:
            mock_cv.return_value = self.df
            mock_metrics.return_value = pd.DataFrame({'rmse': [0.5]})
            
            best_model, best_params, best_rmse = train_until_converged(self.df, max_trials=5, rmse_threshold=1.5)
        
        # 测试最终返回的模型、参数和RMSE
        self.assertIsNotNone(best_model)
        self.assertEqual(best_params, {'fourier_order': 5, 'changepoint_scale': 0.01})
        self.assertEqual(best_rmse, 0.5)
        
    @patch('load_predictor.Prophet', return_value=MagicMock(spec=Prophet))
    def test_train_until_converged_no_cross_validation(self, MockProphet):
        """测试没有交叉验证时的行为"""
        
        # 模拟 Prophet 返回的模型
        mock_prophet_instance = MockProphet.return_value
        
        # 模拟预测过程
        mock_prophet_instance.fit.return_value = None
        mock_prophet_instance.predict.return_value = self.df
        mock_prophet_instance.add_seasonality.return_value = None
        mock_prophet_instance.make_future_dataframe.return_value = self.df
        
        # 模拟性能计算
        y_true = self.df['y'].values[24:48]
        y_pred = self.df['y'].values[24:48]
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        
        # 测试没有交叉验证的情况
        best_model, best_params, best_rmse = train_until_converged(self.df, max_trials=5, rmse_threshold=1.5)
        
        # 检查返回值
        self.assertIsNone(best_model)
        self.assertNotEqual(best_params, {'fourier_order': 5, 'changepoint_scale': 0.01})
        self.assertNotEqual(best_rmse, rmse)


if __name__ == "__main__":
    unittest.main()