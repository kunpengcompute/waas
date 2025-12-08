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
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/waasbooster"))
import boost_log as logging
from quota_calculator import PIDController

class TestPIDController(unittest.TestCase):

    def test_initialization(self):
        pid = PIDController(kp=1.0, ki=0.1, kd=0.01)
        self.assertEqual(pid.kp, 1.0)
        self.assertEqual(pid.ki, 0.1)
        self.assertEqual(pid.kd, 0.01)
        self.assertEqual(pid.max_output, float('inf'))
        self.assertEqual(pid.min_output, -float('inf'))
        self.assertEqual(pid.integral, 0)
        self.assertEqual(pid.prev_err, 0)
        self.assertEqual(pid.prev_truth, None)

    def test_update_no_error(self):
        pid = PIDController(kp=1.0, ki=0.1, kd=0.01)
        output = pid.update(target=10, truth=10, dt=1)
        self.assertEqual(output, 0)

    def test_update_with_error(self):
        pid = PIDController(kp=1.0, ki=0.1, kd=0.01)
        output = pid.update(target=10, truth=5, dt=1)
        self.assertGreater(output, 0)
        self.assertLess(output, pid.max_output)

    def test_update_integral_limit(self):
        pid = PIDController(kp=1.0, ki=0.1, kd=0.01, max_output=10, min_output=-10)
        # Simulate error accumulation
        for _ in range(100):
            pid.update(target=10, truth=0, dt=1)
        self.assertEqual(pid.integral, 0)

    def test_update_derivative(self):
        pid = PIDController(kp=1.0, ki=0.1, kd=0.01)
        # Initially no change in truth, should result in zero derivative term
        output1 = pid.update(target=10, truth=5, dt=1)
        output2 = pid.update(target=10, truth=5, dt=1)
        self.assertEqual(output1, output2 - 0.45)

        # Introducing a change in truth
        output3 = pid.update(target=10, truth=3, dt=1)
        self.assertNotEqual(output3, output2)

    def test_clipping_output(self):
        pid = PIDController(kp=1.0, ki=0.1, kd=0.01, max_output=5, min_output=-5)
        output = pid.update(target=100, truth=0, dt=1)
        self.assertEqual(output, 5)  # Output is clipped to max_output

        output = pid.update(target=-100, truth=0, dt=1)
        self.assertEqual(output, -5)  # Output is clipped to min_output

    def test_update_zero_dt(self):
        pid = PIDController(kp=1.0, ki=0.1, kd=0.01)
        output = pid.update(target=10, truth=5, dt=0)
        self.assertEqual(output, 5.0)  # Should handle zero dt without error

if __name__ == "__main__":
    unittest.main()