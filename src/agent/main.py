"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent main
"""

import argparse
import logging
import threading

import uvicorn

import util
from agent_http.server import create_app
from agent_http.store import PodSnapshotStore
from sample import PerfCount
from data_process import DataProcessor
from layers.numa_reduction import NumaReduction
from handlers.core_handler import CoreHandler
from handlers.soc_handler import SocHandler
from messengers.ipmi_messenger import IpmiMessenger as Messenger
from handler import Handler
from data_recorder import DataRecorder
from http_server_runner import HttpServerRunner
from sampling_worker import SamplingWorker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s'
)

MAX_INTERVAL=10
MIN_INTERVAL=0.01


def _get_args():
    parser = argparse.ArgumentParser(description="waasagent")
    parser.add_argument("-i", "--interval", metavar="INTERVAL", type=float,
        default=1, help="Sample Interval in second, default 1s")
    parser.add_argument("-o", "--output", metavar="OUTPUT", type=str,
        default="", help="Output file path, default ./data.csv")
    parser.add_argument("-m", "--maxrows", metavar="MAXROWS", type=int,
                        default=100000, help="Max rows in one output file, default 10000, \
if there is more data, it will be saved in another file(s).")
    parser.add_argument(
        "--http-host", default="127.0.0.1",
        help="HTTP listen host, default 127.0.0.1",
    )
    parser.add_argument(
        "--http-port", type=int, default=18080,
        help="HTTP listen port, default 18080",
    )
    return parser.parse_args()


def _get_interval(interval):
    if interval > MAX_INTERVAL:
        logging.error("Interval greater than max value, using ", MAX_INTERVAL)
        return MAX_INTERVAL
    elif interval < MIN_INTERVAL:
        logging.error("Interval smaller than min value, using ", MIN_INTERVAL)
        return MIN_INTERVAL
    else:
        return interval


def _create_counter(cgroup_paths):
    return PerfCount(cgroup_paths=cgroup_paths)


def _run_agent(worker, http_runner, store, stop_event):
    try:
        http_runner.start()
        worker.run()
    finally:
        stop_event.set()
        store.close()
        http_runner.stop()


def main():
    args = _get_args()
    interval = _get_interval(args.interval)

    processor = DataProcessor()

    # 按numa聚合特征
    processor.add_porcesser("numa_reduction", [NumaReduction()])

    messenger = Messenger()

    handler = Handler()
    handler.add_handler(util.Weapon.CORE.value, CoreHandler())
    handler.add_handler(util.Weapon.SOC.value, SocHandler())

    recorder = None
    if args.output:
        recorder = DataRecorder(args.output, args.maxrows)

    store = PodSnapshotStore()
    stop_event = threading.Event()
    worker = SamplingWorker(
        store=store,
        stop_event=stop_event,
        counter_factory=_create_counter,
        interval=interval,
        processor=processor,
        messenger=messenger,
        handler=handler,
        recorder=recorder,
    )
    config = uvicorn.Config(
        create_app(store),
        host=args.http_host,
        port=args.http_port,
        log_level="info",
    )
    http_runner = HttpServerRunner(
        server=uvicorn.Server(config),
        store=store,
        stop_event=stop_event,
    )
    _run_agent(worker, http_runner, store, stop_event)


if __name__ == "__main__":
    main()
