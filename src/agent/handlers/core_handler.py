"""
Copyright (c) Huawei Technologies Co., Ltd. 2025. All rights reserved.
Create: 2025-10-21
Description: waas agent sub handler
"""
import logging
import subprocess
from typing import List
from handler import BaseHandler

from weapon.core_group import CoreGroup

_CORE_CMD_TEMPLATE = "regtool set {first_core_id} {last_core_id} {reg_items_str}"
_REG_ITEM_TEMPLATE = "group{reg_id}=0x{value_hex}"

class CoreHandler(BaseHandler):
    def apply(self, advice: List[CoreGroup]) -> None:
        """
        执行CoreGroup对应的regtool命令：单个CoreGroup对应一条命令（含多个reg_item）
        命令格式：regtool set {first_core_id} {last_core_id} group{id1}=0x{val1} group{id2}=0x{val2}...
        """
        logging.debug(f"[CoreHandler] Applying core advice: {len(advice)} groups")
        if not advice:
            return

        for core_group in advice:
            # 跳过无效核ID范围或无寄存器项的分组
            if (core_group.first_core_id > core_group.last_core_id
                    or not core_group.reg_items):
                logging.debug(
                    f"[CoreHandler] Skip invalid core group: core_range=[{core_group.first_core_id}-{core_group.last_core_id}], "
                    f"reg_count={len(core_group.reg_items)}"
                )
                continue

            # 拼接所有寄存器项（groupX=0xval）
            reg_items_str = " ".join([
                _REG_ITEM_TEMPLATE.format(
                    reg_id=item.reg_id,
                    value_hex=f"{item.write_value:016x}"  # 沿用之前约定：16位补0小写十六进制
                ) for item in core_group.reg_items
            ])

            # 拼接完整命令
            cmd = _CORE_CMD_TEMPLATE.format(
                first_core_id=core_group.first_core_id,
                last_core_id=core_group.last_core_id,
                reg_items_str=reg_items_str
            )

            try:
                # 执行命令：无shell、30秒超时、捕获输出
                subprocess.run(
                    cmd.split(), check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    encoding="utf-8", timeout=30
                )
                logging.info(f"[CoreHandler] Command executed successfully: {cmd}")
            except subprocess.CalledProcessError as e:
                logging.error(
                    f"[CoreHandler] Command failed (code={e.returncode}): {cmd} | Error: {e.stderr.strip()}"
                )
            except subprocess.TimeoutExpired:
                logging.error(f"[CoreHandler] Command timed out (30s): {cmd}")
            except Exception as e:
                logging.error(f"[CoreHandler] Command exception: {cmd} | Exception: {str(e)}")
