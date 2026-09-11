from dataclasses import dataclass

from ..models import CommunitySharingProvider
from .base import CommunitySharingClient
from .dmm import DebridMediaManager

__all__ = ["TARGETS", "CommunitySharingClient", "Target", "get"]


@dataclass(frozen=True)
class Target:
    key: CommunitySharingProvider
    name: str
    client: type[CommunitySharingClient]
    needs_key: bool = False


TARGETS: dict[CommunitySharingProvider, Target] = {
    CommunitySharingProvider.DMM: Target(
        key=CommunitySharingProvider.DMM,
        name="Debrid Media Manager",
        client=DebridMediaManager,
    ),
}


def get(key: str) -> Target | None:
    try:
        return TARGETS[CommunitySharingProvider(key)]
    except (KeyError, ValueError):
        return None
