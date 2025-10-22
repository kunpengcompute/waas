"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent data process
"""
import copy

class Layer():
    def __init__(self):
        pass


    def process(self, data):
        return data


class DataProcessor():
    def __init__(self):
        pass
        self.processors = {}


    def add_porcesser(self, name:str, layers:list):
        self.processors[name] = layers

    
    def process(self, data, name=""):
        if name:
            processors = {name : self.processors[name]}
        else:
            processors = self.processors

        result = {}
        for processor_name, processor in processors.items():
            tmp_data = copy.deepcopy(data)
            for layer in processor:
                tmp_data = layer.process(tmp_data)
            result[processor_name] = tmp_data

        return result
