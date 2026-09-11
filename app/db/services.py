import sqlite3
import time

from .models import ServiceRow


class ServiceTable:
    """A provider keyed by name, with an optional API key and an on/off flag.

    Debrid services and community sharing targets have the same shape, so the
    queries live here once. The table name is a class attribute, never a
    parameter, so nothing interpolates a caller's string into SQL.
    """

    table: str
    requires_key: bool

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def all(self, enabled_only: bool = True) -> list[ServiceRow]:
        sql = f"select * from {self.table}"
        if enabled_only:
            sql += " where enabled = 1"
        return [
            ServiceRow.from_row(r)
            for r in self.conn.execute(sql + " order by id").fetchall()
        ]

    def get(self, provider: str) -> ServiceRow | None:
        row = self.conn.execute(
            f"select * from {self.table} where provider = ?", (provider,)
        ).fetchone()
        return ServiceRow.from_row(row) if row else None

    def save(self, provider: str, api_key: str | None, enabled: bool) -> None:
        existing = self.get(provider)
        with self.conn:
            if existing is None:
                if not api_key and self.requires_key:
                    return
                self.conn.execute(
                    f"insert into {self.table} (provider, api_key, enabled, created_at)"
                    " values (?, ?, ?, ?)",
                    (provider, api_key, int(enabled), time.time()),
                )
            else:
                self.conn.execute(
                    f"update {self.table} set api_key = ?, enabled = ? where provider = ?",
                    (api_key or existing.api_key, int(enabled), provider),
                )

    def delete(self, provider: str) -> None:
        with self.conn:
            self.conn.execute(
                f"delete from {self.table} where provider = ?", (provider,)
            )
