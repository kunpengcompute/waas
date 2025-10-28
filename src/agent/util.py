import struct
from data_process import DataProcessor

MAX_INT_FOR_UINT32 = 2 ** 32 - 1

def packup(group_features, timestamp):
    """
    一组指标取值，加上时间戳打成一个包。
    指标编码顺序参考DataProcessor.keys()，也即键的插入顺序（python 3.7+版本以上支持）
    """
    packed_bytes = b''
    # 前8个字节是时间戳
    packed_bytes += struct.pack('>d', timestamp)
    for metric_name, metric_value in group_features.items():
        # 以后每4/8字节存储一个数值
        if metric_name.isupper():
            # 原始指标用8字节无符号整数
            packed = struct.pack(">Q", metric_value)
        else:
            # 复合指标用4字节浮点数
            packed = struct.pack(">f", metric_value)
        packed_bytes += packed
    return packed_bytes

def unpack(packed_bytes, group_keys):
    """
    一批字节数据恢复原值（仅作示例，实际应在bmc中解码）
    group_keys是DataProcessor.keys()的子集，且出现顺序与packed_bytes一致。从而可以根据group_keys选取对应长度字节数据进行解码
    """
    group_features = {}
    for metric_name in group_keys:
        if metric_name not in DataProcessor.features.keys():
            raise Exception("Unknown metric %s, it is not in DataProcessor.keys()!" % metric_name)
        if metric_name.isupper():
            group_features[metric_name] = struct.unpack(">Q", packed_bytes[:8])[0]
        else:
            group_features[metric_name] = struct.unpack(">f", packed_bytes[:4])[0]
    return group_features