"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent setting parameters
"""
from abc import ABC, abstractmethod

class BaseHandler(ABC):
    """抽象基类：定义处理器的统一接口"""
    def __init__(self):
        pass

    @abstractmethod
    def apply(self, advice):
        pass

class Handler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.handlers = {}

    def apply(self, advice):
        """
        advice是字典，每个key对应一种下发工具，例如regtool、devmem等
        """
        for name in advice:
            if name not in self.handlers:
                logging.warning("No handler for %s implemented, will not apply parameters of this type." % name)
                continue
            if len(advice[name]) > 0:
                self.handlers[name].apply(advice[name])


    def add_handler(self, name:str, handler:BaseHandler):
        """
        记录每个regtool和devmem下发工具类
        """
        self.handlers[name] = handler