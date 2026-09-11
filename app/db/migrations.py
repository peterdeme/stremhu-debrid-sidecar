import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(os.environ.get("SIDECAR_DB", "/data/sidecar.db"))

MIGRATIONS: list[str] = [
    """
    create table if not exists settings (
        key   text primary key,
        value text not null
    );

    create table if not exists admin_credentials (
        id            integer primary key check (id = 1),
        password_hash text not null,
        salt          text not null,
        created_at    real not null
    );

    create table if not exists debrids (
        id         integer primary key autoincrement,
        provider   text not null,
        api_key    text not null,
        enabled    integer not null default 1,
        created_at real not null,
        unique (provider)
    );

    create table if not exists sharing (
        id         integer primary key autoincrement,
        provider   text not null,
        api_key    text,
        enabled    integer not null default 1,
        created_at real not null,
        unique (provider)
    );

    create table if not exists pushed (
        provider  text not null,
        info_hash text not null,
        name      text,
        pushed_at real not null,
        primary key (provider, info_hash)
    );

    create table if not exists published (
        info_hash    text primary key,
        name         text,
        published_at real not null,
        hashlist_url text
    );

    create table if not exists runs (
        id          integer primary key autoincrement,
        job         text not null,
        started_at  real not null,
        finished_at real,
        error       text
    );

    create table if not exists decisions (
        run_id    integer not null references runs(id) on delete cascade,
        name      text,
        info_hash text,
        outcome   text not null,
        detail    text,
        provider  text
    );

    create index if not exists decisions_run on decisions(run_id);
    create index if not exists runs_started on runs(started_at desc);
    """,
]


def connect(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma journal_mode = wal")
    conn.execute("pragma foreign_keys = on")
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    version = conn.execute("pragma user_version").fetchone()[0]
    for index, script in enumerate(MIGRATIONS[version:], start=version + 1):
        conn.executescript(script)
        conn.execute(f"pragma user_version = {int(index)}")
        conn.commit()
    return conn.execute("pragma user_version").fetchone()[0]
