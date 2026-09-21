import time
from dataclasses import dataclass, field
from enum import Enum, StrEnum

from .debrid import Account


class JobName(StrEnum):
    SYNC_TO_DEBRID = "sync_to_debrid"
    PUBLISH_TO_COMMUNITY = "publish_to_community"


class Outcome(str, Enum):
    PUSHED = "pushed"
    ALREADY_CACHED = "already cached"
    ALREADY_PUSHED = "already pushed"
    TOO_BIG = "over size limit"
    BARELY_WATCHED = "barely watched"
    NOT_SCENE_FORMAT = "not scene formatted"
    NO_RESOLUTION = "no resolution in the name"
    NO_LANGUAGE_TAG = "no language tag in the name"
    NO_FILE = "file no longer on disk"
    NO_TORRENT = "torrent no longer stored"
    HASH_MISMATCH = "hash mismatch"
    FAILED = "failed"


@dataclass
class Decision:
    name: str
    info_hash: str
    outcome: Outcome
    detail: str = ""
    provider: str | None = None


@dataclass
class RunResult:
    job: JobName
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    decisions: list[Decision] = field(default_factory=list)
    error: str | None = None
    accounts: dict[str, Account] = field(default_factory=dict)

    @property
    def counts(self) -> dict[Outcome, int]:
        out: dict[Outcome, int] = {}
        for d in self.decisions:
            out[d.outcome] = out.get(d.outcome, 0) + 1
        return out

    def decide(self, *args, **kwargs) -> None:
        self.decisions.append(Decision(*args, **kwargs))
