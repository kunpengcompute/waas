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

import logging
logging.getLogger('cmdstanpy').disabled = True
import pandas as pd
import numpy as np
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
from datetime import datetime, timedelta, timezone
import boost_log as logging


def mean_squared_error(y_true, y_pred):
    """手动实现 MSE"""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    if y_true.shape != y_pred.shape:
        raise ValueError("y_true 和 y_pred 的形状必须一致")
    return np.mean((y_true - y_pred) ** 2)


def train_until_converged(df, max_trials=5, rmse_threshold=1.5):
    """模型训练"""
    best_model = None
    best_rmse = float('inf')
    best_params = None
    fourier_orders = [5, 10, 20]
    changepoint_scales = [0.01, 0.1, 0.5]
    use_cross_validation = len(df) >= 2 * 48
    cor = len(df) // 48
    trial_count = 0

    for order in fourier_orders:
        for scale in changepoint_scales:
            if trial_count >= max_trials:
                return best_model, best_params, best_rmse

            logging.debug('fourier_order=%s, changepoint_scale=%s', order, scale)
            model = Prophet(
                daily_seasonality=False,
                weekly_seasonality=False,
                yearly_seasonality=False,
                changepoint_prior_scale=scale,
            )
            model.add_seasonality(name='daily_30min', period=1, fourier_order=order)
            model.fit(df)
            if use_cross_validation:
                try:
                    df_cv = cross_validation(model, initial=f'{cor-1} day', period='12 hours', horizon='12 hours')
                    df_p = performance_metrics(df_cv)
                    rmse = df_p['rmse'].mean()
                except Exception as e:
                    logging.warning('cross validation failed for: %s', e)
                    continue
            else:
                df_train = df.iloc[:24]
                df_val = df.iloc[24:]
                future = model.make_future_dataframe(periods=24, freq='30min')
                forecast = model.predict(future)
                y_pred = forecast.iloc[-24:]['yhat'].values
                y_true = df_val['y'].values
                mse = mean_squared_error(y_true, y_pred)
                rmse = np.sqrt(mse)
            logging.debug('current RMSE: %s', rmse)

            if rmse < best_rmse:
                best_rmse = rmse
                best_model = model
                best_params = {'fourier_order': order, 'changepoint_scale': scale}
                if rmse <= rmse_threshold:
                    logging.debug('model converaged, search terminated')
                    return best_model, best_params, best_rmse
            trial_count += 1
    
    return best_model, best_params, best_rmse


def get_forecast_load(load_data):
    """模型预测"""
    pod_forecast = {}
    data_qualified, pod_data = data_pre(load_data)
    if not data_qualified:
        return None

    for pod_path, pod_value in pod_data.items():
        if pod_value is not None and not pod_value.empty:
            try:
                model, params, final_rmse = train_until_converged(pod_value)
                future = model.make_future_dataframe(periods=48, freq='30min')
                forecast = model.predict(future)

                # 获取最后48步预测
                forecast_tail = forecast.tail(48).copy()

                # 合并真实值
                merged = forecast_tail.merge(
                    pod_value[['ds', 'y']], on='ds', how='left'
                )

                # 计算原值一半
                half_real = merged['y'] * 0.5
                merged.loc[merged['y'].isna(), 'yhat'] = merged.loc[merged['y'].isna(), 'yhat'].clip(lower=0)

                mask_has_real = merged['y'].notna()
                merged.loc[mask_has_real, 'yhat'] = np.maximum.reduce([
                    merged.loc[mask_has_real, 'yhat'],
                    half_real[mask_has_real],
                    np.zeros(mask_has_real.sum())
                ])

                result = [
                    [ts.strftime('%Y-%m-%d %H:%M:%S'), value]
                    for ts, value in zip(merged['ds'], merged['yhat'])
                ]
                pod_forecast[pod_path] = result

            except Exception as e:
                logging.info('pod %s not support forecast', pod_path)

    return pod_forecast


def data_pre(load_data):
    """数据处理"""
    period = 48
    pod_data = {}
    data_qualified = False
    if not load_data:
        return data_qualified, {}
    for pod_path, pod_info in load_data.items():
        pod_data.update({pod_path: None})
        half_hour_avg_value = list(pod_info['half_hour_avg'])
        if len(half_hour_avg_value) >= period:
            node_indices = [i for i, item in enumerate(half_hour_avg_value) if item[2] is None]
            if node_indices:
                last_node_indices = max(node_indices)
                pod_values = [items[2] for items in half_hour_avg_value[last_node_indices+1:]]
                pod_time = [items[1] for items in half_hour_avg_value[last_node_indices+1:]]
            else:
                pod_values = [items[2] for items in half_hour_avg_value]
                pod_time = [items[1] for items in half_hour_avg_value]
            cor = int(len(pod_values) / period)
            if cor >= 1:
                data_qualified = True
                concluded_value = pod_values[-period * cor:]
                concluded_time = pod_time[-period * cor:]
                start_time = (concluded_time[0] - timedelta(minutes=30)).strftime("%Y-%m-%d")
                timestamp = pd.date_range(start=start_time, periods=period * cor, freq='30min')
                values = np.array(concluded_value)
                pod_data.update({pod_path: pd.DataFrame({'ds': timestamp, 'y': values})})
        else:
            continue
    return data_qualified, pod_data
