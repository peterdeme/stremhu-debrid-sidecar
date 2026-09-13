import datetime
import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .config.config import Config

KNOWN_ALEMBIC_REVISIONS = {"3a7b9c1d2e3f"}


class SchemaError(RuntimeError):
    pass


@dataclass(frozen=True)
class Playback:
    info_hash: str
    played_at: str
    torrent_name: str
    file_name: str
    file_index: int | None
    imdb_id: str | None


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_schema(conn: sqlite3.Connection) -> str:
    try:
        revision = conn.execute("select version_num from alembic_version").fetchone()[0]
    except sqlite3.Error as e:
        raise SchemaError(f"not a stremhu database: {e}") from e
    for table in ("playback_histories", "torrent_files"):
        try:
            conn.execute(f"select 1 from {table} limit 1")
        except sqlite3.Error as e:
            raise SchemaError(f"stremhu table {table!r} is missing: {e}") from e
    return revision


def recent_playbacks(
    conn: sqlite3.Connection, limit: int = 200, since_hours: int | None = None
) -> list[Playback]:
    cutoff = None
    if since_hours:
        cutoff = (
            # stremhu writes naive local timestamps, so the cutoff has to be
            # built the same way. A tz-aware now() would be the bug.
            datetime.datetime.now()  # noqa: DTZ005
            - datetime.timedelta(hours=since_hours)
        ).strftime("%Y-%m-%d %H:%M:%S.%f")

    rows = conn.execute(
        """
        select f.info_hash, max(p.created_at) as played_at, p.torrent_name,
               p.file_name, p.file_index, p.imdb_info
        from playback_histories p
        join torrent_files f
          on f.indexer_id = p.indexer_id and f.torrent_id = p.torrent_id
        where f.torrent_bytes is not null
          and (? is null or p.created_at >= ?)
        group by f.info_hash
        order by played_at desc
        limit ?
        """,
        (cutoff, cutoff, limit),
    ).fetchall()

    import json

    out = []
    for r in rows:
        imdb = None
        try:
            imdb = (json.loads(r["imdb_info"] or "{}") or {}).get("imdb_id")
        except ValueError:
            pass
        out.append(
            Playback(
                info_hash=r["info_hash"].lower(),
                played_at=r["played_at"],
                torrent_name=r["torrent_name"] or "",
                file_name=r["file_name"] or "",
                file_index=r["file_index"],
                imdb_id=imdb,
            )
        )
    return out


def torrent_blob(conn: sqlite3.Connection, info_hash: str) -> bytes | None:
    row = conn.execute(
        "select torrent_bytes from torrent_files where info_hash = ? limit 1",
        (info_hash,),
    ).fetchone()
    return bytes(row["torrent_bytes"]) if row and row["torrent_bytes"] else None


def bdecode(data: bytes, i: int = 0):
    c = data[i : i + 1]
    if c == b"i":
        end = data.index(b"e", i)
        return int(data[i + 1 : end]), end + 1
    if c == b"l":
        out, i = [], i + 1
        while data[i : i + 1] != b"e":
            item, i = bdecode(data, i)
            out.append(item)
        return out, i + 1
    if c == b"d":
        out, i = {}, i + 1
        while data[i : i + 1] != b"e":
            key, i = bdecode(data, i)
            val, i = bdecode(data, i)
            out[key] = val
        return out, i + 1
    if c.isdigit():
        colon = data.index(b":", i)
        n = int(data[i:colon])
        return data[colon + 1 : colon + 1 + n], colon + 1 + n
    raise ValueError(f"bad bencode at offset {i}")


def _info_span(data: bytes) -> tuple[int, int] | None:
    i = data.find(b"4:info")
    if i < 0:
        return None
    start = i + len(b"4:info")
    try:
        _, end = bdecode(data, start)
    except ValueError, IndexError, KeyError:
        return None
    return start, end


def info_hash_of(blob: bytes) -> str | None:
    span = _info_span(blob)
    if not span:
        return None
    return hashlib.sha1(blob[span[0] : span[1]]).hexdigest()


def _info_dict(blob: bytes) -> dict | None:
    span = _info_span(blob)
    if not span:
        return None
    try:
        info, _ = bdecode(blob, span[0])
    except ValueError, IndexError, KeyError:
        return None
    return info if isinstance(info, dict) else None


def total_size(blob: bytes) -> int | None:
    info = _info_dict(blob)
    if info is None:
        return None
    try:
        if b"length" in info:
            return info[b"length"]
        return sum(f.get(b"length", 0) for f in info.get(b"files", []) or [])
    except AttributeError, TypeError:
        return None


def fetched_fraction(
    blob: bytes, file_index: int | None, downloads: Path
) -> float | None:
    info = _info_dict(blob)
    if info is None:
        return None

    try:
        name = info[b"name"].decode(errors="replace")
        files = info.get(b"files")
        if files:
            if file_index is None or file_index >= len(files):
                return None
            entry = files[file_index]
            path = downloads.joinpath(
                name, *[p.decode(errors="replace") for p in entry[b"path"]]
            )
            declared = entry[b"length"]
        else:
            path = downloads / name
            declared = info[b"length"]
    except KeyError, AttributeError, TypeError:
        return None

    if not declared:
        return None
    try:
        allocated = path.stat().st_blocks * 512
    except OSError:
        return None
    return min(allocated / declared, 1.0)


def status(cfg: Config) -> dict:
    conn = None
    try:
        conn = connect(cfg.database_path)
        revision = check_schema(conn)
        playbacks = len(recent_playbacks(conn))
        return {
            "ok": True,
            "revision": revision,
            "known": revision in KNOWN_ALEMBIC_REVISIONS,
            "playbacks": playbacks,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        if conn is not None:
            conn.close()
