import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceRow:
    """A configured debrid service or community sharing target."""

    id: int
    provider: str
    api_key: str | None
    enabled: bool
    created_at: float

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ServiceRow:
        return cls(
            id=row["id"],
            provider=row["provider"],
            api_key=row["api_key"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class Credentials:
    password_hash: str
    salt: str
    created_at: float

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Credentials:
        return cls(
            password_hash=row["password_hash"],
            salt=row["salt"],
            created_at=row["created_at"],
        )
