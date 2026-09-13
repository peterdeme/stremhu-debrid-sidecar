from dataclasses import dataclass

from ..models import DebridProvider
from .base import DebridClient
from .torbox import Torbox

__all__ = ["DEBRIDS", "Debrid", "DebridClient", "get"]


@dataclass(frozen=True)
class Debrid:
    key: DebridProvider
    name: str
    client: type[DebridClient]
    key_hint: str


DEBRIDS: dict[DebridProvider, Debrid] = {
    DebridProvider.TORBOX: Debrid(
        key=DebridProvider.TORBOX,
        name="TorBox",
        client=Torbox,
        key_hint="A TorBox irányítópultján találod, a Beállítások alatt.",
    ),
}


def get(key: str) -> Debrid | None:
    try:
        return DEBRIDS[DebridProvider(key)]
    except KeyError, ValueError:
        return None
