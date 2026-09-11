from ..db import Store
from ..models import Account
from . import get


class DebridStatus:
    def __init__(self):
        self._by_provider: dict[str, dict] = {}

    def all(self) -> dict[str, dict]:
        return self._by_provider

    def record(self, provider: str, account: Account) -> None:
        self._by_provider[provider] = {"ok": True, "account": account}

    def forget(self, provider: str) -> None:
        self._by_provider.pop(provider, None)

    async def refresh(self, store: Store) -> None:
        results: dict[str, dict] = {}
        for row in store.debrid.all(enabled_only=False):
            debrid = get(row.provider)
            if debrid is None or row.api_key is None:
                continue
            try:
                async with debrid.client(row.api_key) as client:
                    results[row.provider] = {
                        "ok": True,
                        "account": await client.account(),
                    }
            except Exception as e:
                results[row.provider] = {
                    "ok": False,
                    "error": f"{type(e).__name__}: {e}",
                }
        self._by_provider = results
