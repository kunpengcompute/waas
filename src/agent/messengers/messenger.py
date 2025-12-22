"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent data process
"""

from abc import ABC, abstractmethod

class Messenger(ABC):
    def __init__(self):
        self.last_output = b""

    '''
    将data字典打包成字节序列，分批调用某种渠道发送到bmc。data字典格式如下：
    {
      "start_time":  datetime.datetime对象
      "all":  {
            group_id:  {
                metric_name: metric_value,
                ...
            },
            ...
        }
    }
    '''
    @abstractmethod
    def send_data(self, data):
        pass

    @abstractmethod
    def get_advice(self):
        pass