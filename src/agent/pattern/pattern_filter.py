import json
from data_process import Layer
from pattern.calculators import _cpy, _div, _add, IPC_VAL_MAX

class PatternFilter(Layer):
    def __init__(self):
        self.features = {
            "INST_RETIRED"                 : _cpy("INST_RETIRED"),
            # "instructions.retired:u/a"     : _sub("instructions_retired", "instructions_retired_k") / _cpy("instructions_retired"),
            "branch.ratio"                 : _div("BR_RETIRED", "INST_RETIRED"),
            "ldst.ratio"                   : _add("LD_SPEC", "ST_SPEC") / _cpy("INST_SPEC"),
            "ld/st"                        : _div("LD_SPEC", "ST_SPEC"),
            "ldst.exclusive/ldst"          : _add("LDREX_SPEC", "STREX_SPEC") / _add("LD_SPEC", "ST_SPEC"),
            "int.ratio"                    : _div("INT_SPEC", "INST_SPEC"),
            "fp.ratio"                     : _div("FP_SPEC", "INST_SPEC"),
            # "vector.ratio"                 : _add("SIMD_INST_SPEC", "SVE_INST_SPEC", "ASE_INST_SPEC") / _cpy("INST_SPEC"),
            "CPU_CYCLES"                   : _cpy("CPU_CYCLES"),
            # "cpu.cycles:u/a"               : _sub("CPU_CYCLES", "CPU_CYCLES_KERNEL") / _cpy("CPU_CYCLES"),
            "cpu.ipc"                      : _div("INST_RETIRED", "CPU_CYCLES", "IPC") / IPC_VAL_MAX,
            # "cpu.ipc:u"                    : _sub("instructions_retired", "instructions_retired_k") / _sub("CPU_CYCLES", "CPU_CYCLES_KERNEL") / IPC_VAL_MAX,
            "branch.mpi"                   : _div("BR_MIS_PRED_RETIRED", "INST_RETIRED"),
            "l1i.mpi"                      : _div("L1I_CACHE_REFILL", "INST_RETIRED"),
            "l1d.mpi"                      : _div("L1D_CACHE_REFILL", "INST_RETIRED"),
            "l2i.mpi"                      : _div("L2I_CACHE_REFILL", "INST_RETIRED"),
            "l2d.mpi"                      : _div("L2D_CACHE_REFILL", "INST_RETIRED"),
            # "voluntary_csw.ratio"          : _cpy("voluntary_csw") / _add("voluntary_csw", "involuntary_csw"),
            # "voluntary_csw/M-cycles"       : _div("voluntary_csw", "CPU_CYCLES") * 10 ** 6,
            # "tcp_recv_packets/M-instrs"    : _div("TCP_RECV_PACKETS", "instructions_retired") * 10 ** 6,
            # "tcp_send_bytes/M-instrs"      : _div("TCP_SEND_BYTES", "instructions_retired") * 10 ** 6,
        }

    def process(self, data):
        pattern_data = {
            "start_time": str(data['start_time']),
            "stop_time": str(data['stop_time']),
            "all": {
                group_id: {} for group_id in data['all'].keys()
            }
        }

        for group_id in data['all']:
            group_data = {
                metric_name.upper(): metric_dict['count']
                for metric_name, metric_dict in data['all'][group_id].items()
            }
            for metric_name, metric_calculator in self.features.items():
                pattern_data['all'][group_id][metric_name] = metric_calculator(group_data)

        print("\n +++++++ PATTERN DATA FILTER DISPLAY++++++++")
        print(pattern_data)
        print("\n +++++++ PATTERN DATA FILTED++++++++")
        return pattern_data
