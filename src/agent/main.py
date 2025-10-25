"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent main
"""

import argparse
import psutil

from sample import PerfCount
from data_process import DataProcessor, Layer
from messenger import Messenger
from handler import Handler
from data_recorder import DataRecorder


MAX_INTERVAL=10
MIN_INTERVAL=0.01


def _get_args():
    parser = argparse.ArgumentParser(description="waasagent")
    parser.add_argument("-c", "--cpus", metavar="CPU", type=str,
        default="", help="List of CPU IDs to sample, default all")
    parser.add_argument("-i", "--interval", metavar="INTERVAL", type=float,
        default=1, help="Sample Interval in second, default 1s")
    parser.add_argument("-o", "--output", metavar="OUTPUT", type=str,
        default="", help="Output file path, default ./data.csv")
    parser.add_argument("-m", "--maxrows", metavar="MAXROWS", type=int,
                        default=100000, help="Max rows in one output file, default 10000, \
if there is more data, it will be saved in another file(s).")
    return parser.parse_args()


def _get_cpus(cpus):
    logical_cores = psutil.cpu_count(logical=True)
    cpu_list = []
    if not cpus:
        return cpu_list

    try:
        if '-' in cpus:
            l = cpus.split('-')
            start, end = int(l[0]), int(l[1])
            if start >= 0 and end < logical_cores:
                cpu_list = list(range(start, end + 1))
            else:
                raise ValueError("cpu core out of range")
        else:
            l = cpus.split()
            for c in l:
                core = int(c)
                if core >= 0 and core < logical_cores:
                    cpu_list.append(core)
                else:
                    raise ValueError("cpu core out of range")
    except Exception as e:
        print("Parse cpu list error: ", e, "\n Using all cpus")
        cpu_list = []

    return cpu_list


def _get_interval(interval):
    if interval > MAX_INTERVAL:
        print("Interval greater than max value, using ", MAX_INTERVAL)
        return MAX_INTERVAL
    elif interval < MIN_INTERVAL:
        print("Interval smaller than min value, using ", MIN_INTERVAL)
        return MIN_INTERVAL
    else:
        return interval


def main():
    args = _get_args()

    cpu_list = _get_cpus(args.cpus)
    _counter = PerfCount(cpu_list=cpu_list)
    _processor = DataProcessor()

    _dummy_layer = Layer()
    _processor.add_porcesser("dummy", [_dummy_layer])
    _messenger = Messenger()
    _handler = Handler()
    recorder = None
    if args.output != "":
        recorder = DataRecorder(args.output, args.maxrows)

    while True:
        _counter.count(_get_interval(args.interval))
        data = _counter.get_data()
        if recorder:
            recorder.insert(data)
        payload = _processor.process(data)
        print(payload)

        _messenger.send_data(payload)
        advice = _messenger.get_advice()

        if advice:
            _handler.apply(advice)


if __name__ == "__main__":
    main()
