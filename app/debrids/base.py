from abc import ABC, abstractmethod
from typing import Self

from ..models import Account, AccountTorrent


class DebridClient(ABC):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        return None

    @abstractmethod
    async def account(self) -> Account: ...

    @abstractmethod
    async def cached(self, hashes: list[str]) -> set[str]: ...

    @abstractmethod
    async def add_torrent(
        self, blob: bytes, name: str, seed: int | None
    ) -> int | None: ...

    @abstractmethod
    async def account_torrents(self) -> list[AccountTorrent]: ...
