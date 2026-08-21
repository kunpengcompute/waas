from datetime import datetime

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


_RAW_REASON_NAMES = (
    "base",
    "compute",
    "l2",
    "l3",
    "membw",
    "tlb",
    "frontend",
)


def raw_reason_name_from_code(reason_code: int) -> str | None:
    if type(reason_code) is not int or reason_code not in range(
        len(_RAW_REASON_NAMES)
    ):
        return None
    return _RAW_REASON_NAMES[reason_code]


class InterferenceResponse(StrictModel):
    version: str = "v1"
    node_name: str = Field(min_length=1)
    reason_codes: tuple[int, ...]

    @classmethod
    def empty(cls, node_name: str) -> "InterferenceResponse":
        return cls(
            node_name=node_name,
            reason_codes=(),
        )
