import sqlite3
import time

from .models import Credentials


class AuthStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def credentials(self) -> Credentials | None:
        row = self.conn.execute(
            "select * from admin_credentials where id = 1"
        ).fetchone()
        return Credentials.from_row(row) if row else None

    def set_password(self, password_hash: str, salt: str) -> None:
        with self.conn:
            self.conn.execute(
                "insert into admin_credentials (id, password_hash, salt, created_at)"
                " values (1, ?, ?, ?)"
                " on conflict(id) do update set"
                " password_hash = excluded.password_hash, salt = excluded.salt",
                (password_hash, salt, time.time()),
            )
