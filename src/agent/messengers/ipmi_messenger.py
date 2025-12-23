"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent data messenger (with ipmitool)
"""

import subprocess
import logging
import util
from messengers.messenger import Messenger

IPMI_PREFIX = "ipmitool raw 0x30 0x93 0xdb 0x07 0x00 0x35"
BUFFER_CLEARING_COMMAND = "ipmitool raw 0x30 0x93 0xdb 0x07 0x00 0x35 0x00"
CHUNK_SIZE = 240 # ipmi命令限制，一次最多255字节数据

class IpmiMessenger(Messenger):
    def __init__(self):
        super().__init__()

    def send_data(self, data):
        # 获取帧大小+时间戳+有效数据 字节序列
        packed_bytes = util.packup_request(data['all'], data['start_time'].timestamp(), data.get('cores', 384))
        command_list = []
        for i in range(0, len(packed_bytes), CHUNK_SIZE):
            # 获取当前分片
            chunk = packed_bytes[i:i + CHUNK_SIZE]
            chunk_length = len(chunk)

            length_byte = "0x%02x" % chunk_length
            data_bytes_str = " ".join("0x%02x" % byte for byte in chunk)

            command = "%s %s %s" % (IPMI_PREFIX, length_byte, data_bytes_str)
            command_list.append(command)

        logging.debug("\n 总共分割为 %d 条命令" % len(command_list))

        for i, cmd in enumerate(command_list):
            logging.debug("\n Running %s(th) command: %s..." % (i, cmd))
            result = subprocess.run(cmd.split(), shell=False, capture_output=True, timeout=30)
            if result.returncode != 0:
                # 命令执行失败，执行清理命令
                clear_result = subprocess.run(BUFFER_CLEARING_COMMAND.split(), shell=False, capture_output=True, timeout=30)

                error_msg = "命令 %s: %s 执行失败，回显: %s\n" % (i, cmd, result.stdout)
                if result.stderr:
                    error_msg += "原始输出：%s" % (result.stderr.decode("utf-8", errors="ignore"))

                # 添加清理命令执行结果信息
                if clear_result.returncode != 0:
                    error_msg += "\n清理命令执行也失败，返回码: %d" % clear_result.returncode
                else:
                    error_msg += "\n已执行清理命令清空缓冲区"

                raise Exception(error_msg)
            if i == len(command_list) - 1 and result.stdout != self.last_output: # 减少刷屏
                # 记录末次执行结果并打印
                logging.info("[IpmiMessenger] Output: %s..." % result.stdout)
                self.last_output = result.stdout

        return self.last_output

    def get_advice(self):
        return util.unpack_response(self.last_output)