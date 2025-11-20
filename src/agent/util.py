import logging
import struct
from data_process import DataProcessor

MAX_INT_FOR_UINT32 = 2 ** 32 - 1

'''
打包出 帧大小（四字节）+ 时间戳（8字节）+各核数据 的字节序列
'''
def packup(groups, timestamp):
    # 前8个字节是时间戳
    packed_bytes = struct.pack('>d', timestamp)
    for group_id in sorted(groups.keys()):
        group_data = groups[group_id]
        group_bytes = packup_chunk(group_data) # 后续拼出所有group上的字节信息
        packed_bytes += group_bytes
        logging.debug("The original data for group %s is %s" % (group_id, group_data))
        logging.debug("The unpacked bytes for group %s is %s" % (group_id, unpack(group_bytes,
                                                                                       DataProcessor.features.keys())))
    frame_prefix = struct.pack(">I", len(packed_bytes))
    return frame_prefix + packed_bytes

def packup_chunk(group_features):
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

def unpack(chunk_bytes, group_keys):
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
            group_features[metric_name] = struct.unpack(">Q", chunk_bytes[start_index:start_index+8])[0]
            start_index += 8
        else:
            group_features[metric_name] = struct.unpack(">f", chunk_bytes[start_index:start_index+4])[0]
            start_index += 4
    return group_features