from dataclasses import dataclass
from enum import StrEnum


class CommunitySharingProvider(StrEnum):
    DMM = "dmm"


@dataclass(frozen=True)
class SharedItem:
    filename: str
    info_hash: str
    size: int
