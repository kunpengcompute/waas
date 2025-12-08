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

class PIDController:
    def __init__(self, kp, ki, kd, max_output=float('inf'), min_output=-float('inf')):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_output = max_output
        self.min_output = min_output

        self.integral = 0
        self.prev_err = 0
        self.prev_truth = None


    def update(self, target, truth, dt):
        err = target - truth

        # 计算比例项
        p = self.kp * err

        # 计算积分项，限制积分大小
        integral = err * dt
        self.integral += integral
        self.integral = max(min(self.integral, self.max_output/self.ki), self.min_output/self.ki)
        i = self.ki * self.integral

        # 计算微分项
        if dt > 0:
            de = (err - self.prev_err) / dt
        else:
            de = 0
        if self.prev_truth is not None and dt > 0:
            de = -(truth - self.prev_truth) / dt
        self.prev_truth = truth
        d = self.kd * de

        output = p + i + d

        clipped_output = max(min(output, self.max_output), self.min_output)
        # 输出饱和时回退本次积分结果（可选）
        if clipped_output != output:
            self.integral -= integral

        self.prev_err = err

        return clipped_output