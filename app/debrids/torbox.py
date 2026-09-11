import httpx

from ..models import Account, AccountTorrent, Plan
from .base import DebridClient

API = "https://api.torbox.app/v1/api"
USER_AGENT = "stremhu-debrid-sidecar/0.1"


class TorboxError(RuntimeError):
    pass


PLANS = {
    0: Plan("Free", None, None, None),
    1: Plan("Essential", 200, 24, 3),
    2: Plan("Pro", 1000, 720, 10),
    3: Plan("Standard", 200, 336, 5),
}
UNKNOWN_PLAN = Plan("ismeretlen", None, None, None)


class Torbox(DebridClient):
    def __init__(self, api_key: str, timeout: float = 120.0):
        if not api_key:
            raise TorboxError("no TorBox API key configured")
        super().__init__(api_key)
        self._client = httpx.AsyncClient(
            base_url=API,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": USER_AGENT,
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def cached(self, hashes: list[str]) -> set[str]:
        found: set[str] = set()
        for i in range(0, len(hashes), 100):
            chunk = ",".join(hashes[i : i + 100])
            r = await self._client.get(
                "/torrents/checkcached", params={"hash": chunk, "format": "list"}
            )
            if r.status_code != 200:
                raise TorboxError(f"checkcached returned {r.status_code}")
            for item in r.json().get("data") or []:
                h = (item or {}).get("hash")
                if h:
                    found.add(h.lower())
        return found

    async def account(self) -> Account:
        r = await self._client.get("/user/me")
        if r.status_code != 200:
            raise TorboxError(f"user/me returned {r.status_code}")
        d = r.json().get("data") or {}
        raw = d.get("plan")
        plan_id = raw if isinstance(raw, int) else -1
        plan = PLANS.get(plan_id, UNKNOWN_PLAN)
        extra = d.get("additional_concurrent_slots") or 0
        return Account(
            plan=plan,
            plan_id=plan_id,
            slots=(plan.slots + extra) if plan.slots is not None else None,
            subscribed=bool(d.get("is_subscribed")),
            expires_at=d.get("premium_expires_at"),
        )

    async def account_torrents(self) -> list[AccountTorrent]:
        r = await self._client.get("/torrents/mylist", params={"bypass_cache": "true"})
        if r.status_code != 200:
            raise TorboxError(f"mylist returned {r.status_code}")
        out = []
        for t in r.json().get("data") or []:
            h = (t.get("hash") or "").lower()
            if len(h) == 40:
                out.append(
                    AccountTorrent(
                        info_hash=h,
                        name=t.get("name") or "",
                        size=t.get("size") or 0,
                        state=t.get("download_state") or "",
                    )
                )
        return out

    async def add_torrent(self, blob: bytes, name: str, seed: int | None) -> int | None:
        data = {}
        if seed is not None:
            data["seed"] = str(seed)
        safe = "".join(c for c in name if c.isalnum() or c in " ._-")[:120] or "torrent"
        files = {"file": (f"{safe}.torrent", blob, "application/x-bittorrent")}
        r = await self._client.post("/torrents/createtorrent", data=data, files=files)
        body = {}
        try:
            body = r.json()
        except ValueError:
            pass
        if r.status_code != 200 or not body.get("success"):
            detail = body.get("detail") or body.get("error") or r.text[:200]
            raise TorboxError(f"createtorrent {r.status_code}: {detail}")
        return (body.get("data") or {}).get("torrent_id")
