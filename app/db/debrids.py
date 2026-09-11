import time

from .services import ServiceTable


class DebridStore(ServiceTable):
    """The configured debrid services, and what has been uploaded to each.

    `pushed` is keyed by provider as well as hash: a torrent on one service
    says nothing about another.
    """

    table = "debrids"
    requires_key = True

    def pushed_hashes(self, provider: str) -> set[str]:
        return {
            r[0]
            for r in self.conn.execute(
                "select info_hash from pushed where provider = ?", (provider,)
            )
        }

    def mark_pushed(
        self, provider: str, info_hash: str, name: str | None = None
    ) -> None:
        with self.conn:
            self.conn.execute(
                "insert or ignore into pushed"
                " (provider, info_hash, name, pushed_at) values (?, ?, ?, ?)",
                (provider, info_hash, name, time.time()),
            )

    def count_pushed(self, provider: str | None = None) -> int:
        if provider:
            return self.conn.execute(
                "select count(*) from pushed where provider = ?", (provider,)
            ).fetchone()[0]
        return self.conn.execute(
            "select count(distinct info_hash) from pushed"
        ).fetchone()[0]
