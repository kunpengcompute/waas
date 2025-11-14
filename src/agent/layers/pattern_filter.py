import json
import logging
from data_process import Layer
from calculators import _cpy, _div, _add, IPC_VAL_MAX

class PatternFilter(Layer):
    def __init__(self):
        self.features = [
            "INST_RETIRED"               ,
            # "instructions.retired:u/a" ,
            "branch.ratio"               ,
            "ldst.ratio"                 ,
            "ld/st"                      ,
            "ldst.exclusive/ldst"        ,
            "int.ratio"                  ,
            "fp.ratio"                   ,
            "vector.ratio"             ,
            "CPU_CYCLES"                 ,
            # "cpu.cycles:u/a"           ,
            "cpu.ipc"                    ,
            # "cpu.ipc:u"                ,
            "branch.mpi"                 ,
            "l1i.mpi"                    ,
            "l1d.mpi"                    ,
            "l2i.mpi"                    ,
            "l2d.mpi"                    ,
            # "voluntary_csw.ratio"      ,
            # "voluntary_csw/M-cycles"   ,
            # "tcp_recv_packets/M-instrs",
            # "tcp_send_bytes/M-instrs"  ,
        ]

    def process(self, data):
        pattern_data = {}
        for group_id in data:
            pattern_data[group_id] = {}
            for metric_name in self.features:
                pattern_data[group_id][metric_name] = data[group_id][metric_name]

        logging.debug("[PatternFilter] Data filtered is %s", pattern_data)
        return pattern_data
