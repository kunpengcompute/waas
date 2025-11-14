"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent data process
"""
import copy
import logging
from calculators import _cpy, _add, _sub, _div, IPC_VAL_MAX

class Layer():
    def __init__(self):
        pass


    def process(self, data):
        return data


class DataProcessor():
    features = {
        "INST_RETIRED"                   : _cpy("INST_RETIRED"),
        "instructions.retired:u/a"       : _div("INST_RETIRED", "INST_RETIRED_ALL"),
        "branch.ratio"                   : _div("BR_RETIRED", "INST_RETIRED"),
        "ldst.ratio"                     : _add("LD_SPEC", "ST_SPEC") / _cpy("INST_SPEC"),
        "ld/st"                          : _div("LD_SPEC", "ST_SPEC"),
        "ldst.exclusive/ldst"            : _add("LDREX_SPEC", "STREX_SPEC") / _add("LD_SPEC", "ST_SPEC"),
        "int.ratio"                      : _div("INT_SPEC", "INST_SPEC"),
        "fp.ratio"                       : _div("FP_SPEC", "INST_SPEC"),
        "vector.ratio"                   : _add("SIMD_INST_SPEC", "SVE_INST_SPEC", "ASE_INST_SPEC") / _cpy("INST_SPEC"),
        "cpu.cycles:u/a"                 : _div("CPU_CYCLES", "CPU_CYCLES_ALL"),
        "cpu.ipc"                        : _div("INST_RETIRED", "CPU_CYCLES") / IPC_VAL_MAX, # 参与运算各数据默认是user态
        "branch.mpi"                     : _div("BR_MIS_PRED_RETIRED", "INST_RETIRED"),
        "l1i.mpi"                        : _div("L1I_CACHE_REFILL", "INST_RETIRED"),
        "l1d.mpi"                        : _div("L1D_CACHE_REFILL", "INST_RETIRED"),
        "l2i.mpi"                        : _div("L2I_CACHE_REFILL", "INST_RETIRED"),
        "l2d.mpi"                        : _div("L2D_CACHE_REFILL", "INST_RETIRED"),
        # "voluntary_csw.ratio"          : _cpy("voluntary_csw") / _add("voluntary_csw", "involuntary_csw"),
        # "voluntary_csw/M-cycles"       : _div("voluntary_csw", "CPU_CYCLES") * 10 ** 6,
        # "tcp_recv_packets/M-instrs"    : _div("TCP_RECV_PACKETS", "instructions_retired") * 10 ** 6,
        # "tcp_send_bytes/M-instrs"      : _div("TCP_SEND_BYTES", "instructions_retired") * 10 ** 6,
        "tlb2i.mpi"                      : _div("L2I_TLB_REFILL", "INST_RETIRED"),
        "l1i.mr"                         : _div("L1I_CACHE_REFILL", "L1I_CACHE"),
        "l1d.mr"                         : _div("L1D_CACHE_REFILL", "L1D_CACHE"),
        "l1d.refer/l1i.refer"            : _div("L1D_CACHE", "L1I_CACHE"),
        "l1d.refer/tlb1d.refer"          : _div("L1D_CACHE", "L1D_TLB"),
        "branch.mr"                      : _div("BR_MIS_PRED_RETIRED", "BR_RETIRED"),
        "load.ratio"                     : _div("LD_SPEC", "INST_SPEC"),
        "store.ratio"                    : _div("ST_SPEC", "INST_SPEC"),
        "scalar.ratio"                   : _add("INT_SPEC", "FP_SPEC") / _cpy("INST_SPEC"),
        "simd.ratio"                     : _div("SIMD_INST_SPEC", "INST_SPEC"),
        "sve.ratio"                      : _div("SVE_INST_SPEC", "INST_SPEC"),
        "neon.ratio"                     : _div("ASE_INST_SPEC", "INST_SPEC"),
        "load_exclusive.ratio"           : _div("LDREX_SPEC", "INST_SPEC"),
        "tlb1d.mr"                       : _div("L1D_TLB_REFILL", "L1D_TLB"),
        "l3.mr"                          : _div("LL_CACHE_MISS", "LL_CACHE"),
        "store_exclusive.ratio"          : _div("STREX_SPEC", "INST_SPEC"),
        "l3.mpi"                         : _div("LL_CACHE_MISS", "INST_RETIRED"),
        "tlb1d.mpi"                      : _div("L1D_TLB_REFILL", "INST_RETIRED"),
        "branch.rpi"                     : _div("BR_RETIRED", "INST_RETIRED"),
        "tlb2d.rpi"                      : _div("L2D_TLB", "INST_RETIRED"),

    }

    def __init__(self):
        self.processors = {}



    def aggregate(self, data):
        """将传入原始指标处理得到self.features中关心的指标"""
        aggregated_data = {}
        for group_id in data.keys():
            aggregated_data[group_id] = {}
            group_data = {
                metric_name: metric_dict['count']
                for metric_name, metric_dict in data[group_id].items()
            }
            for metric_name, metric_calculator in self.features.items():
                aggregated_data[group_id][metric_name] = metric_calculator(group_data)

        return aggregated_data

    def process(self, data, name=""):
        _data = self.aggregate(data.get('all', {}))
        if name:
            processors = {name : self.processors[name]}
        else:
            processors = self.processors

        tmp_data = None
        for processor_name, processor in processors.items():
            logging.debug("Processing with processor %s", processor_name)
            tmp_data = copy.deepcopy(_data)
            for layer in processor:
                tmp_data = layer.process(tmp_data)

        return {
            "start_time": data['start_time'],
            "stop_time": data['stop_time'],
            "all": tmp_data
        }

    def add_porcesser(self, name:str, layers:list):
        self.processors[name] = layers