import logging
import struct
from enum import Enum
from typing import ClassVar, List, Tuple, Dict, Optional
from data_process import DataProcessor
from weapon.soc_group import SocGroup
from weapon.core_group import CoreGroup, CoreRegItem

# 全局宏定义变量
PLACEHOLDER_0 = 0x00
LABEL_MAP = {
    "base": 0,
    "compute": 1,
    "l2": 2,
    "l3": 3,
    "membw": 4,
    "tlb": 5,
    "frontend": 6,
}

class Weapon(Enum):
    SOC = "SOC"
    CORE = "CORE"

'''
打包出 帧大小（四字节）+ 时间戳（8字节）+各核数据 的字节序列
'''
def packup_request(groups, timestamp, cores):
    # 前8个字节是时间戳
    packed_bytes = struct.pack('>d', timestamp) # 8字节双精度浮点数
    packed_bytes += struct.pack(">H", cores) # 2字节无符号整数
    for group_id in sorted(groups.keys()):
        group_data = groups[group_id]
        group_bytes = packup_request_chunk(group_data) # 后续拼出所有group上的字节信息
        packed_bytes += group_bytes
        logging.debug("The original data for group %s is %s" % (group_id, group_data))
        logging.debug("The unpacked bytes for group %s is %s" % (group_id, unpack_request(group_bytes,
                                                                                          DataProcessor.features.keys())))
    frame_prefix = struct.pack(">I", len(packed_bytes))
    return frame_prefix + packed_bytes

def packup_request_chunk(group_features):
    """
    一组指标取值，加上时间戳打成一个包。
    指标编码顺序参考DataProcessor.keys()，也即键的插入顺序（python 3.7+版本以上支持）
    """
    chunk_bytes = b''
    for metric_name, metric_value in group_features.items():
        # 以后每4/8字节存储一个数值
        if metric_name.isupper():
            # 原始指标用8字节无符号整数
            packed = struct.pack(">Q", int(metric_value))
        else:
            # 复合指标用4字节浮点数
            packed = struct.pack(">f", metric_value)
        chunk_bytes += packed
    return chunk_bytes

def unpack_request(chunk_bytes, group_keys):
    """
    一批字节数据恢复原值（仅作示例，实际应在bmc中解码）
    group_keys是DataProcessor.keys()的子集，且出现顺序与chunk_bytes一致。从而可以根据group_keys选取对应长度字节数据进行解码
    """
    group_features = {}
    start_index = 0
    for metric_name in group_keys:
        if metric_name not in DataProcessor.features.keys():
            raise Exception("Unknown metric %s, it is not in DataProcessor.keys()!" % metric_name)
        if metric_name.isupper():
            group_features[metric_name] = struct.unpack(">Q", chunk_bytes[start_index:start_index + 8])[0]
            start_index += 8
        else:
            group_features[metric_name] = struct.unpack(">f", chunk_bytes[start_index:start_index + 4])[0]
            start_index += 4
    return group_features

# 响应数据预处理函数
def preprocess_response(raw_data: bytes) -> Optional[bytes]:
    """
    预处理原始字节数据（支持带空格/换行的非连续格式）转换为连续字节流以用于解码
    :param raw_data: 原始字节数据
    :return: 处理后的字节流（成功，包括空字节b''）；None（失败）
    """
    logging.debug("Starting data preprocessing")

    # 输入类型校验
    if not isinstance(raw_data, bytes):
        logging.debug("Preprocessing failed: input must be bytes type")
        return None  # 失败时返回None，下同

    try:
        # 字节转字符串 → 清除所有空白字符
        data_str = raw_data.decode('utf-8').strip()
        cleaned_str = ''.join(data_str.split())
        logging.debug(f"Cleaned hex string: {cleaned_str[:100]}...")  # 截断长日志

        # 校验十六进制字符串长度（必须为偶数）
        if len(cleaned_str) % 2 != 0:
            logging.debug(f"Preprocessing failed: odd hex length ({len(cleaned_str)})")
            return None

        # 转换为连续字节流
        processed_bytes = bytes.fromhex(cleaned_str)
        logging.debug(f"Preprocessing succeeded: {len(processed_bytes)}B processed")
        return processed_bytes

    except ValueError as e:
        logging.debug(f"Preprocessing failed: hex conversion error - {str(e)}")
        return None


def unpack_core(core_bytes: bytes, group_count: int) -> List[CoreGroup]:
    """
    解码核寄存器字节数据，生成核寄存器分组列表
    解析指定数量的核寄存器分组，自动跳过无效分组或解析失败的分组
    :param core_bytes: 核寄存器原始字节数据
    :param group_count: 核寄存器分组总数
    :return: 解析成功的CoreGroup对象列表
    """
    core_groups: List[CoreGroup] = []
    offset = 0
    total_len = len(core_bytes)
    logging.debug(f"Decoding core: group_count={group_count}, input_len={total_len}B")

    for idx in range(group_count):
        if offset >= total_len:
            logging.debug(f"Core group {idx+1}: no remaining data")
            break
        try:
            group = CoreGroup.deserialize(core_bytes[offset:])
            core_groups.append(group)
            offset += CoreGroup.SIZE + group.reg_count * CoreRegItem.SIZE
            logging.debug(f"Core group {idx+1} decoded: {group}")
        except ValueError as e:
            logging.debug(f"Core group {idx+1} decode failed: {e}, skip")
            offset += min(CoreGroup.SIZE, total_len - offset)
    return core_groups


def unpack_soc(soc_bytes: bytes, group_count: int) -> List[SocGroup]:
    """
    解码SOC寄存器字节数据，生成SOC寄存器分组列表
    解析指定数量的SOC寄存器分组，自动跳过寄存器数为0的无效分组
    :param soc_bytes: SOC寄存器原始字节数据
    :param group_count: SOC寄存器分组总数
    :return: 解析成功的SocGroup对象列表
    """
    soc_groups: List[SocGroup] = []
    offset = 0
    total_len = len(soc_bytes)
    group_len = SocGroup.SIZE
    logging.debug(f"Decoding SOC: group_count={group_count}, input_len={total_len}B")

    for idx in range(group_count):
        group_start = offset
        group_end = group_start + group_len
        if group_end > total_len:
            logging.debug(f"SOC group {idx+1}: insufficient data")
            break
        try:
            group = SocGroup.deserialize(soc_bytes[group_start:group_end])
            if group.reg_count != PLACEHOLDER_0:
                soc_groups.append(group)
            logging.debug(f"SOC group {idx+1} decoded: {group}")
        except ValueError as e:
            logging.debug(f"SOC group {idx+1} decode failed: {e}, skip")
        offset = group_end
    return soc_groups


def unpack_response_content(content: Optional[bytes]) -> Dict[str, List]:
    """
    主解码函数：预处理原始数据 + 分别解码核/SOC寄存器 + 组织返回结果
    自动处理数据预处理、分组解析逻辑，返回结构化的解码结果
    :param content: 待解码的原始字节数据（支持带空格/换行的非连续格式），如果是None，则返回空调优手段
    :return: 字典格式的解码结果，包含核寄存器分组列表和SOC寄存器分组列表
             键名分别为"Weapon.CORE.value"和"Weapon.SOC.value"对应的值
    """
    if content is None or len(content) < 1:
        logging.debug(f"Decode failed: no core or soc group content.")
        return {Weapon.CORE.value: [], Weapon.SOC.value: []}

    core_groups = unpack_core(
        content[1:],
        content[0]
    )

    # 计算SOC起始位置（核心数据总长度 = 分组计数字节 + 所有核心分组字节）
    core_total_len = 1 + sum(CoreGroup.SIZE + g.reg_count * CoreRegItem.SIZE for g in core_groups)
    soc_meta_start = core_total_len

    # 解码SOC参数
    soc_groups = []
    if soc_meta_start + 1 <= len(content):
        soc_groups = unpack_soc(
            content[soc_meta_start + 1:],
            content[soc_meta_start]
        )
    else:
        logging.debug("No SOC group count data")

    logging.debug(f"Decode completed: {len(core_groups)} core groups, {len(soc_groups)} SOC groups")
    return {
        Weapon.CORE.value: core_groups,
        Weapon.SOC.value: soc_groups
    }
