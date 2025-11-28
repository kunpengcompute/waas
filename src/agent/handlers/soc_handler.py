"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent sub handler
"""
import logging
import subprocess
from typing import List
from handler import BaseHandler

from weapon.soc_group import SocGroup

_SOC_CMD_TEMPLATE = "devmem 0x{addr_hex} w 0x{value_hex}"

class SocHandler(BaseHandler):
    def apply(self, advice: List[SocGroup]) -> None:
        """
        解析 SocGroup 生成 devmem 命令：每个寄存器地址对应一条命令
        命令格式：devmem 0x{addr_hex} w 0x{value_hex}
        规则：addr_hex 不补0（原生长度），value_hex 补0到16位，均为小写十六进制
        """
        logging.debug(f"[SocHandler] Applying SOC advice: {len(advice)} groups")
        if not advice:
            return

        for soc_group in advice:
            # 跳过寄存器数为0的无效分组
            if soc_group.reg_count <= 0:
                logging.debug(
                    f"[SocHandler] Skip invalid SOC group: reg_count={soc_group.reg_count}, base_addr=0x{soc_group.base_addr:x}"
                )
                continue

            # 生成该分组下所有寄存器地址和命令
            for reg_idx in range(soc_group.reg_count):
                # 计算当前寄存器地址（base_addr + 索引 * 地址偏移）
                current_addr = soc_group.base_addr + reg_idx * soc_group.addr_offset
                # 地址转十六进制（不补0，小写）
                addr_hex = f"{current_addr:x}"
                # 值转十六进制（补0到16位，小写）
                value_hex = f"{soc_group.write_value:016x}"

                # 拼接命令
                cmd = _SOC_CMD_TEMPLATE.format(
                    addr_hex=addr_hex,
                    value_hex=value_hex
                )

                try:
                    # 执行命令：无shell、30秒超时、捕获输出
                    subprocess.run(
                        cmd.split(), check=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        encoding="utf-8", timeout=30
                    )
                    logging.info(f"[SocHandler] Command executed successfully: {cmd}")
                except subprocess.CalledProcessError as e:
                    logging.error(
                        f"[SocHandler] Command failed (code={e.returncode}): {cmd} | Error: {e.stderr.strip()}"
                    )
                except subprocess.TimeoutExpired:
                    logging.error(f"[SocHandler] Command timed out (30s): {cmd}")
                except Exception as e:
                    logging.error(f"[SocHandler] Command exception: {cmd} | Exception: {str(e)}")