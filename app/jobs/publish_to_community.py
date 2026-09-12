from .. import community_sharing, debrids
from ..models import JobName, Outcome, RunResult, SharedItem
from .base import Job


class PublishToCommunityJob(Job):
    name = JobName.PUBLISH_TO_COMMUNITY

    async def execute(self, result: RunResult) -> None:
        targets = self.store.community.all()
        if not targets:
            result.error = "nincs beállítva megosztási cél"
            self.log.warning("no sharing target configured")
            return

        library = await self._library()
        already = self.store.community.published_hashes()
        for h, (name, _) in library.items():
            if h in already:
                result.decide(name, h, Outcome.ALREADY_PUSHED, "korábban megosztva")

        new = [
            SharedItem(name, h, size)
            for h, (name, size) in library.items()
            if h not in already
        ]
        self.log.info(
            "library scanned",
            extra={
                "library": len(library),
                "already_published": len(already & library.keys()),
                "new": len(new),
                "targets": len(targets),
            },
        )
        if not new:
            return

        for row in targets:
            target = community_sharing.get(row.provider)
            if target is None:
                self.log.warning(
                    "unknown sharing target", extra={"provider": row.provider}
                )
                continue
            try:
                async with target.client(row.api_key) as client:
                    url = await client.publish(new)
            except Exception as e:
                self.log.exception("publish failed", extra={"provider": row.provider})
                result.decide(
                    "", "", Outcome.FAILED, f"{type(e).__name__}: {e}", row.provider
                )
                continue

            self.store.community.mark_published(
                [(i.info_hash, i.filename) for i in new], url
            )
            self.log.info(
                "published",
                extra={"provider": row.provider, "items": len(new), "url": url},
            )
            for i in new:
                result.decide(
                    i.filename, i.info_hash, Outcome.PUSHED, url, row.provider
                )

    async def _library(self) -> dict[str, tuple[str, int]]:
        library: dict[str, tuple[str, int]] = {}
        for row in self.store.debrid.all():
            debrid = debrids.get(row.provider)
            if debrid is None or row.api_key is None:
                continue
            async with debrid.client(row.api_key) as client:
                for t in await client.account_torrents():
                    library.setdefault(t.info_hash, (t.name, t.size))
        return library
