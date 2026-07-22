from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class OnlinePod(StrictModel):
    namespace: str
    name: str
    uid: str = Field(min_length=1)
    cgroup_path: str = Field(min_length=1)


class OnlinePodsRequest(StrictModel):
    version: str = Field(min_length=1)
    node_name: str = Field(min_length=1)
    timestamp: datetime
    pods: tuple[OnlinePod, ...]


class OnlinePodsResponse(StrictModel):
    accepted: bool
    message: str | None = None


class InterferenceReason(str, Enum):
    UNKNOWN = "unknown"
    L3 = "l3"
    MB = "mb"
    CPU = "cpu"


_CONTROLLER_REASON_BY_CODE = {
    0: InterferenceReason.UNKNOWN,
    1: InterferenceReason.CPU,
    2: InterferenceReason.CPU,
    3: InterferenceReason.L3,
    4: InterferenceReason.MB,
    5: InterferenceReason.CPU,
    6: InterferenceReason.CPU,
}


def controller_reason_from_code(reason_code: int) -> InterferenceReason:
    return _CONTROLLER_REASON_BY_CODE.get(reason_code, InterferenceReason.UNKNOWN)


class InterferenceItem(StrictModel):
    pod_uid: str = Field(min_length=1)
    score: float


class InterferenceResponse(StrictModel):
    version: str = "v1"
    node_name: str = Field(min_length=1)
    reason: InterferenceReason
    ttl_seconds: int = Field(ge=0)
    items: tuple[InterferenceItem, ...]

    @classmethod
    def unknown(cls, node_name: str) -> "InterferenceResponse":
        return cls(
            node_name=node_name,
            reason=InterferenceReason.UNKNOWN,
            ttl_seconds=0,
            items=(),
        )
