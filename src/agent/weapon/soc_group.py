import struct
from dataclasses import dataclass
from typing import ClassVar

@dataclass
class SocGroup:
    # Class variables
    REG_COUNT_SIZE: ClassVar[int] = 1
    ADDR_SIZE: ClassVar[int] = 8
    OFFSET_SIZE: ClassVar[int] = 8
    VALUE_SIZE: ClassVar[int] = 8
    FORMAT: ClassVar[str] = ">BQQQ"
    SIZE: ClassVar[int] = struct.calcsize(FORMAT)

    # Instance variables
    base_addr: int = 0
    reg_count: int = 0
    addr_offset: int = 0
    write_value: int = 0

    @classmethod
    def deserialize(cls, data: bytes) -> 'SocGroup':
        """Deserialize from bytes"""
        if len(data) < cls.SIZE:
            raise ValueError(f"Data too short: need {cls.SIZE} bytes, got {len(data)}")

        try:
            reg_count, base_addr, addr_offset, write_value = struct.unpack(
                cls.FORMAT,
                data[:cls.SIZE]
            )
            return cls(
                reg_count=reg_count,
                base_addr=base_addr,
                addr_offset=addr_offset,
                write_value=write_value
            )
        except struct.error as e:
            raise ValueError(f"Deserialization failed: {e}") from e

    def __str__(self) -> str:
        return (f"SocGroup(reg_count={self.reg_count}, base_addr=0x{self.base_addr:x}, "
            f"addr_offset=0x{self.addr_offset:x}, write_value=0x{self.write_value:016x})")

    def __repr__(self) -> str:
        return self.__str__()
