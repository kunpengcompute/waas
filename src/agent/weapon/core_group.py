import array
import struct
from typing import List, ClassVar
from dataclasses import dataclass, field

@dataclass
class CoreRegItem:
    reg_id: int
    write_value: int
    
    # Serialization format (big-endian)
    FORMAT: ClassVar[str] = ">BQ"  # uint8_t, uint64_t (big-endian)
    SIZE: ClassVar[int] = struct.calcsize(FORMAT)  # 1 + 8 = 9 bytes
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'CoreRegItem':
        """Deserialize single CoreRegItem from byte stream"""
        if len(data) < cls.SIZE:
            raise ValueError(f"Insufficient data: need {cls.SIZE} bytes, got {len(data)} bytes")
        
        reg_id, write_value = struct.unpack(cls.FORMAT, data[:cls.SIZE])
        return cls(reg_id=reg_id, write_value=write_value)
    
    def __str__(self) -> str:
        return f"CoreRegItem(reg_id={self.reg_id}, write_value=0x{self.write_value:016x})"


@dataclass
class CoreGroup:
    reg_count: int
    first_core_id: int
    last_core_id: int
    reg_items: List[CoreRegItem] = field(default_factory=list)
    
    # Fixed header format (big-endian, excluding GArray pointer)
    FORMAT: ClassVar[str] = ">BHH"  # uint8_t, uint16_t, uint16_t
    SIZE: ClassVar[int] = struct.calcsize(FORMAT)  # 1 + 2 + 2 = 5 bytes
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'CoreGroup':
        """Deserialize CoreGroup from byte stream"""
        if len(data) < cls.SIZE:
            raise ValueError(f"Insufficient header data: need {cls.SIZE} bytes, got {len(data)} bytes")
        
        # Parse header
        reg_count, first_core_id, last_core_id = struct.unpack(
            cls.FORMAT, data[:cls.SIZE]
        )
        
        # Validate register count
        if reg_count < 0:
            raise ValueError(f"Invalid register count: {reg_count}")
        
        # Calculate expected data size
        expected_data_size = cls.SIZE + reg_count * CoreRegItem.SIZE
        
        if len(data) < expected_data_size:
            raise ValueError(f"Incomplete data: need {expected_data_size} bytes, got {len(data)} bytes")
        
        # Parse CoreRegItem array
        reg_items = []
        offset = cls.SIZE
        
        for i in range(reg_count):
            item_data = data[offset:offset + CoreRegItem.SIZE]
            reg_item = CoreRegItem.deserialize(item_data)
            reg_items.append(reg_item)
            offset += CoreRegItem.SIZE
        
        return cls(
            reg_count=reg_count,
            first_core_id=first_core_id,
            last_core_id=last_core_id,
            reg_items=reg_items
        )

    def __str__(self) -> str:
        items_str = ", ".join(str(item) for item in self.reg_items)
        return (f"CoreGroup(reg_count={self.reg_count}, core_range=[{self.first_core_id}, {self.last_core_id}], "
            f"reg_items=[{items_str}])")

    def __repr__(self) -> str:
        return self.__str__()