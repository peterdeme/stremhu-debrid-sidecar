import sqlite3

from .. import debrids, stremhu
from ..debrids import Debrid
from ..debrids.torbox import TorboxError
from ..models import Account, Decision, JobName, Outcome, RunResult
from ..stremhu import Playback
from .base import Job


class SyncToDebridJob(Job):
    name = JobName.SYNC_TO_DEBRID

    async def execute(self, result: RunResult) -> None:
        services = self.store.debrid.all()
        if not services:
            result.error = "nincs beállítva debrid szolgáltatás"
            self.log.warning("no debrid service configured")
            return

        conn = stremhu.connect(self.config.database_path)
        try:
            stremhu.check_schema(conn)
            candidates = stremhu.recent_playbacks(
                conn, since_hours=self.config.lookback_hours
            )
            self.log.info(
                "playbacks collected",
                extra={
                    "candidates": len(candidates),
                    "lookback_hours": self.config.lookback_hours,
                    "providers": len(services),
                },
            )
            for row in services:
                provider = debrids.get(row.provider)
                if provider is None or row.api_key is None:
                    self.log.warning(
                        "skipping unusable debrid service",
                        extra={"provider": row.provider},
                    )
                    result.decide(
                        "",
                        "",
                        Outcome.FAILED,
                        "ismeretlen szolgáltatás",
                        row.provider,
                    )
                    continue
                await self._push_to(provider, row.api_key, conn, candidates, result)
        finally:
            conn.close()

    async def _push_to(
        self,
        provider: Debrid,
        api_key: str,
        conn: sqlite3.Connection,
        candidates: list[Playback],
        result: RunResult,
    ) -> None:
        key = provider.key
        already = self.store.debrid.pushed_hashes(key)
        pending = [p for p in candidates if p.info_hash not in already]
        self.log.info(
            "pending playbacks for provider",
            extra={"provider": key, "pending": len(pending), "seen": len(already)},
        )

        try:
            async with provider.client(api_key) as client:
                account = await client.account()
                result.accounts[key] = account
                if not pending:
                    return

                size_cap = self._size_cap(account)
                cached = await client.cached([p.info_hash for p in pending])

                pushed = 0
                for p in pending:
                    if pushed >= self.config.push_limit:
                        break

                    blob = stremhu.torrent_blob(conn, p.info_hash)
                    if blob is None:
                        result.decide(
                            p.torrent_name, p.info_hash, Outcome.NO_TORRENT, "", key
                        )
                        continue

                    rejection = self._rejection(p, blob, size_cap, key)
                    if rejection is not None:
                        result.decisions.append(rejection)
                        continue

                    is_cached = p.info_hash in cached
                    try:
                        tid = await client.add_torrent(
                            blob, p.torrent_name, self.config.seed_preference
                        )
                    except TorboxError as e:
                        self.log.warning(
                            "add_torrent rejected",
                            extra={
                                "provider": key,
                                "info_hash": p.info_hash,
                                "error": str(e),
                            },
                        )
                        result.decide(
                            p.torrent_name, p.info_hash, Outcome.FAILED, str(e), key
                        )
                        continue

                    self.store.debrid.mark_pushed(key, p.info_hash, p.torrent_name)
                    if not is_cached:
                        pushed += 1
                    result.decide(
                        p.torrent_name,
                        p.info_hash,
                        Outcome.ALREADY_CACHED if is_cached else Outcome.PUSHED,
                        f"id={tid}",
                        key,
                    )
        except Exception as e:
            self.log.exception("provider push failed", extra={"provider": key})
            result.decide("", "", Outcome.FAILED, f"{type(e).__name__}: {e}", key)

    def _size_cap(self, account: Account) -> int | None:
        plan_gb = account.plan.max_download_gb
        cap = plan_gb * 1_000_000_000 if plan_gb else None
        override = self.config.max_torrent_size_bytes
        if override:
            cap = min(cap, override) if cap else override
        return cap

    def _rejection(
        self, p: Playback, blob: bytes, size_cap: int | None, key: str
    ) -> Decision | None:
        computed = stremhu.info_hash_of(blob)
        if computed is None:
            return Decision(
                p.torrent_name,
                p.info_hash,
                Outcome.HASH_MISMATCH,
                "a .torrent nem olvasható",
                key,
            )
        if computed != p.info_hash:
            return Decision(
                p.torrent_name, p.info_hash, Outcome.HASH_MISMATCH, computed, key
            )

        if self.config.min_fetched_fraction > 0:
            fetched = stremhu.fetched_fraction(
                blob, p.file_index, self.config.downloads_path
            )
            if fetched is None:
                return Decision(p.torrent_name, p.info_hash, Outcome.NO_FILE, "", key)
            if fetched < self.config.min_fetched_fraction:
                return Decision(
                    p.torrent_name,
                    p.info_hash,
                    Outcome.BARELY_WATCHED,
                    f"{fetched:.0%}",
                    key,
                )

        size = stremhu.total_size(blob)
        if size and size_cap and size > size_cap:
            return Decision(
                p.torrent_name, p.info_hash, Outcome.TOO_BIG, f"{size / 1e9:.1f}GB", key
            )
        return None
