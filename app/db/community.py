import time

from .services import ServiceTable


class CommunityStore(ServiceTable):
    """Where hashes get published, and which ones already went out.

    `published` is keyed by hash alone: a hash is worth sharing once, wherever
    it happens to live.
    """

    table = "sharing"
    requires_key = False

    def published_hashes(self) -> set[str]:
        return {r[0] for r in self.conn.execute("select info_hash from published")}

    def mark_published(
        self, items: list[tuple[str, str]], hashlist_url: str | None
    ) -> None:
        now = time.time()
        with self.conn:
            self.conn.executemany(
                "insert or ignore into published"
                " (info_hash, name, published_at, hashlist_url) values (?, ?, ?, ?)",
                [(h, name, now, hashlist_url) for h, name in items],
            )

    def count_published(self) -> int:
        return self.conn.execute("select count(*) from published").fetchone()[0]

    def last_hashlist_url(self) -> str | None:
        row = self.conn.execute(
            "select hashlist_url from published where hashlist_url is not null"
            " order by published_at desc limit 1"
        ).fetchone()
        return row[0] if row else None
