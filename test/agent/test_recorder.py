"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent recorder test
"""

import unittest
from unittest import mock
from unittest.mock import patch, mock_open, MagicMock
import os
import shutil
import sys
from collections import deque

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "../../src/agent"))

import data_recorder
import sample

MAX_ROWS=10

class TestSample(unittest.TestCase):
    def setUp(self):
        self._clean_tmp()
        os.mkdir('tmp')
        self.recorder = data_recorder.DataRecorder("tmp/tmp.csv", max_rows=MAX_ROWS)
        self.counter = sample.PerfCount()
        self.counter.count(1)
        self.data = self.counter.get_data()
        super().setUp()


    def tearDown(self):
        self.recorder.close()
        self._clean_tmp()
        super().tearDown()


    def _clean_tmp(self):
        if os.path.exists("tmp"):
            shutil.rmtree('tmp')


    def test_insert(self):
        self.recorder.insert(self.data)

        for i in range(MAX_ROWS * 2):
            self.recorder.insert(self.data)


if __name__ == "__main__":
    unittest.main()