import json
import sqlite3


class ConfigStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def values(self) -> dict:
        return {
            r["key"]: json.loads(r["value"])
            for r in self.conn.execute("select key, value from settings")
        }

    def save(self, values: dict) -> None:
        with self.conn:
            self.conn.executemany(
                "insert into settings (key, value) values (?, ?)"
                " on conflict(key) do update set value = excluded.value",
                [(k, json.dumps(v)) for k, v in values.items()],
            )
