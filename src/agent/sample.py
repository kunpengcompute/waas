"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent counter
"""

from datetime import datetime
import time

import kperf


EVENTS = {
    'user' : [
        [
            'r0008',    # INST_RETIRED
            'r0011',    # CPU_CYCLES
            'r0021',    # BR_RETIRED
            'r0022',    # BR_MIS_PRED_RETIRED
        ],

        [
            'r001b',    # INST_SPEC
            'r0070',    # LD_SPEC
            'r0071',    # ST_SPEC
            'r006c',    # LDREX_SPEC
            'r006f',    # STREX_SPEC
        ],

        [
            'r8040',    # INT_SPEC
            'r8010',    # FP_SPEC
            'r8004',    # SIMD_INST_SPEC
            'r8005',    # ASE_INST_SPEC
            'r8006',    # SVE_INST_SPEC
            'r853e',    # SME_INST_SPEC
        ],

        [
            'l1i_cache',
            'l1i_cache_refill',
            'l1d_cache',
            'l1d_cache_refill',
            'l1i_tlb',
            'l1i_tlb_refill',
        ],

        [
            'l2i_cache',
            'l2i_cache_refill',
            'l2d_cache',
            'l2d_cache_refill',
            'l2i_tlb',
            'l2i_tlb_refill',
        ],

        [
            'l1d_tlb',
            'l1d_tlb_refill',
            'l2d_tlb',
            'l2d_tlb_refill',
        ],
    ],

    'all' : []
}


EVENT_NAME_MAP = {
    'r0008' : 'INST_RETIRED',
    'r0011' : 'CPU_CYCLES',
    'r0021' : 'BR_RETIRED',
    'r0022' : 'BR_MIS_PRED_RETIRED',
    'r001b' : 'INST_SPEC',
    'r0070' : 'LD_SPEC',
    'r0071' : 'ST_SPEC',
    'r006c' : 'LDREX_SPEC',
    'r006f' : 'STREX_SPEC',
    'r8040' : 'INT_SPEC',
    'r8010' : 'FP_SPEC',
    'r8004' : 'SIMD_INST_SPEC',
    'r8005' : 'ASE_INST_SPEC',
    'r8006' : 'SVE_INST_SPEC',
    'r853e' : 'SME_INST_SPEC',
}


class PerfCount():
    def __init__(self, cpu_list=None):
        if cpu_list:
            self.cpu_list = cpu_list
        else:
            self.cpu_list = []

        self.events = []

        self.data = {}
        self.pd = 0

        self.start_time = None
        self.stop_time = None
        self.results = {}

        self._init_event()


    def _init_event(self):
        i = 1
        for group in EVENTS['user']:
            group_num = i
            i+=1
            for event in group:
                self.events.append({
                    'event' : event,
                    'group' : group_num,
                    'excludeUser' : False,
                    'excludeKernel' : True,
                })

        for group in EVENTS['all']:
            group_num = i
            i+=1
            for event in group:
                self.events.append({
                    'event' : event,
                    'group' : group_num,
                    'excludeUser' : False,
                    'excludeKernel' : False,
                })
        
        self.pd = self._open_pd()



    def _open_pd(self):
        evt_list = [ evt['event'] for evt in self.events ]
        evt_attr_list = [ evt['group'] for evt in self.events ]
        #exclude_user_list = [ evt['excludeUser'] for evt in self.events ]
        #exclude_kernel_list = [ evt['excludeKernel'] for evt in self.events ]

        pmu_attr = kperf.PmuAttr(evtList=evt_list, cpuList=self.cpu_list,
            excludeKernel=True, excludeUser=False, evtAttr=evt_attr_list)
        
        pd = kperf.open(kperf.PmuTaskType.COUNTING, pmu_attr)
        if pd == -1:
            print(kperf.error())
            raise ValueError(kperf.error())
        return pd


    def count(self, count_time):
        kperf.enable(self.pd)
        self.start_time = datetime.now()
        time.sleep(count_time)
        self.stop_time = datetime.now()
        kperf.disable(self.pd)

        self.results = kperf.read(self.pd)
        return self.results


    def get_data(self):
        result = {}
        for data in self.results.iter:
            if not result.get(data.cpu):
                result[data.cpu] = {}
            
            if data.evt.startswith('r'):
                evt_name = EVENT_NAME_MAP[data.evt]
            else:
                evt_name = data.evt

            result[data.cpu][evt_name] = {}
            result[data.cpu][evt_name]['count'] = data.count
            result[data.cpu][evt_name]['countPercent'] = data.countPercent

        return {
            "start_time": self.start_time,
            "stop_time": self.stop_time,
            "all": result
        }
