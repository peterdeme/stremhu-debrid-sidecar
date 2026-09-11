from abc import ABC, abstractmethod
from typing import Self

from ..models import SharedItem


class CommunitySharingClient(ABC):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        return None

    @abstractmethod
    async def publish(self, items: list[SharedItem]) -> str | None: ...
