import json
import time

import httpx

from ..lzstring import compress_to_encoded_uri_component
from ..models import SharedItem
from .base import CommunitySharingClient

BASE = "https://debridmediamanager.com"
USER_AGENT = "stremhu-debrid-sidecar/0.1"

TITLE = "stremhu-debrid-sidecar %Y-%m-%d"


class DebridMediaManager(CommunitySharingClient):
    def __init__(self, api_key: str | None = None, timeout: float = 120.0):
        super().__init__(api_key)
        self._timeout = timeout

    async def publish(self, items: list[SharedItem]) -> str | None:
        payload = {
            "title": time.strftime(TITLE),
            "torrents": [
                {"filename": i.filename, "hash": i.info_hash, "bytes": i.size}
                for i in items
            ],
        }
        fragment = compress_to_encoded_uri_component(json.dumps(payload))
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(
                f"{BASE}/api/hashlists",
                json={"url": f"{BASE}/hashlist#{fragment}"},
                headers={"User-Agent": USER_AGENT},
            )
        if r.status_code != 200:
            raise RuntimeError(f"DMM returned {r.status_code}: {r.text[:200]}")
        return r.json().get("shortUrl")
