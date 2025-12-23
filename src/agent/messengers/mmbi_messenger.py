"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent data messenger (with mmbi)
"""

import os
from select import epoll, EPOLLIN, EPOLLRDNORM
from contextlib import contextmanager
import logging
import util
from messengers.messenger import Messenger

MMBI_PATH = "/dev/mmbi0"
POLL_TIMEOUT = 5
POLL_RETRIES = 10
READ_MAX_SIZE = 3000

@contextmanager
def device_handler(path: str):
    fd = None
    try:
        fd = os.open(path, os.O_RDWR | os.O_EXCL, 0o644)
        yield fd
    except (OSError, IOError) as e:
        logging.error(f"Device operation failed: %s" % str(e))
        raise e
    finally:
        if fd is not None:
            os.close(fd)


class MMBIMessenger(Messenger):
    def __init__(self):
        super().__init__()

    def _wait_device(self, fd: int) -> bool:
        """使用epoll等待设备就绪"""
        try:
            with epoll() as poller:
                poller.register(fd, EPOLLIN | EPOLLRDNORM)
                for _ in range(POLL_RETRIES):
                    events = poller.poll(POLL_TIMEOUT)
                    for fileno, event in events:
                        if fileno == fd and event & (EPOLLIN | EPOLLRDNORM):
                            return True
        except IOError as exp:
            logging.error("Epoll error: %s" % str(exp))
        return False

    def send_data(self, data):
        # 获取帧大小+时间戳+有效数据 字节序列
        packed_bytes = util.packup_request(data['all'], data['start_time'].timestamp(), data.get('cores', 384))
        response = b""
        with device_handler(MMBI_PATH) as fd:
            logging.debug("\n Sending data: %s to %s..." % (packed_bytes, MMBI_PATH))
            bytes_written = os.write(fd, packed_bytes)
            logging.debug("Wrote %s bytes to %s..." % (bytes_written, MMBI_PATH))
            if not self._wait_device(fd):
                logging.warning("Device response timeout")
                return None
            response = os.read(fd, READ_MAX_SIZE)
            logging.debug("Read %s bytes from %s..." % (len(response), MMBI_PATH))
        if response != self.last_output:
            logging.info("[MMBIMessenger] Output: %s..." % response)
            self.last_output = response

        return self.last_output

    def get_advice(self):
        return util.unpack_response_content(self.last_output)