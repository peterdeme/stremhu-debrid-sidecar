from dataclasses import dataclass
from enum import IntEnum, StrEnum


class DebridProvider(StrEnum):
    TORBOX = "torbox"


class SeedPreference(IntEnum):
    AUTO = 1
    ALWAYS = 2
    NEVER = 3


@dataclass(frozen=True)
class Plan:
    name: str
    max_download_gb: int | None
    seeding_hours: int | None
    slots: int | None


@dataclass(frozen=True)
class Account:
    plan: Plan
    plan_id: int
    slots: int | None
    subscribed: bool
    expires_at: str | None

    @property
    def seeding_label(self) -> str:
        hours = self.plan.seeding_hours
        if hours is None:
            return "ismeretlen"
        return f"{hours} óra" if hours < 48 else f"{hours // 24} nap"


@dataclass(frozen=True)
class AccountTorrent:
    info_hash: str
    name: str
    size: int
    state: str
