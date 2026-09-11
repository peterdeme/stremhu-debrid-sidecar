"""Six tests, picked by what has actually broken rather than by coverage."""

import pytest

from app import config as config_module
from app import db, stremhu
from app.lzstring import compress_to_encoded_uri_component

PAGES = ["/", "/sync", "/share"]


@pytest.mark.parametrize("path", PAGES)
def test_every_page_renders(client, path):
    """Goes through the real app, so a context key the renderer forgets to
    pass shows up here. Template-level tests build their own context and
    cannot catch that."""
    r = client.get(path)
    assert r.status_code == 200
    assert "stremhu" in r.text


@pytest.mark.parametrize("path", PAGES)
def test_pages_require_a_password(anonymous, path):
    """Asserting on the redirect rather than the final body: following it
    would pass on a wide-open instance too."""
    r = anonymous.get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_settings_round_trip(client, store):
    """Form binding is what breaks when handler signatures change, and they
    have changed three times."""
    client.post(
        "/settings/sync",
        data={
            "push_interval_minutes": "25",
            "lookback_hours": "72",
            "min_fetched_percent": "40",
            "seed_preference": "3",
        },
    )
    cfg = config_module.load(store)
    assert (cfg.push_interval_minutes, cfg.lookback_hours) == (25, 72)
    assert cfg.min_fetched_fraction == 0.4
    assert cfg.push_enabled is False  # unchecked box is absent from the post

    # The publish interval is clamped in code, not merely asked for in the UI.
    client.post("/settings/share", data={"publish_interval_hours": "1"})
    assert config_module.load(store).effective_publish_interval_hours == 24


def test_migrations_apply_from_scratch_and_survive_a_half_applied_one(tmp_path):
    """A failed migration is the one bug that stops the app booting at all.

    executescript commits implicitly, so a script that dies partway leaves its
    earlier tables behind with user_version unchanged, and the next startup
    runs the whole script again. Simulated here by creating one table by hand
    and leaving the version at 0: without idempotent DDL this raises.
    """
    path = tmp_path / "fresh.db"
    conn = db.connect(path)
    # Exactly what a crash after the first statement leaves behind: the real
    # table, the right schema, and user_version still at 0.
    conn.execute("create table settings (key text primary key, value text not null)")
    conn.commit()
    assert conn.execute("pragma user_version").fetchone()[0] == 0

    assert db.migrate(conn) == len(db.MIGRATIONS)
    assert db.migrate(conn) == len(db.MIGRATIONS)

    # The recovery above only exercises the statements before the crash point,
    # so the property itself is asserted directly: every DDL statement guarded.
    for script in db.MIGRATIONS:
        lowered = script.lower()
        for verb in ("create table", "create index"):
            assert lowered.count(verb) == lowered.count(f"{verb} if not exists")

    tables = {
        r[0]
        for r in conn.execute(
            "select name from sqlite_master where type='table' and name not like 'sqlite_%'"
        )
    }
    assert {"settings", "admin_credentials", "debrids", "sharing", "pushed",
            "published", "runs", "decisions"} <= tables


def test_info_hash_of_a_real_torrent_and_of_rubbish():
    """The infohash is the product: a wrong one is a silent rejection. And a
    single unreadable blob must not raise, or it takes out the whole run."""
    info = b"d6:lengthi1024e4:name8:film.mkv12:piece lengthi16384ee"
    blob = b"d8:announce20:http://tracker/annc4:info" + info + b"e"

    import hashlib

    assert stremhu.info_hash_of(blob) == hashlib.sha1(info).hexdigest()
    assert stremhu.total_size(blob) == 1024

    for rubbish in (b"", b"not a torrent", blob[:20], b"d4:infod6:lengthi1e"):
        assert stremhu.info_hash_of(rubbish) is None


def test_lzstring_matches_the_reference_implementation():
    """DMM would happily accept a corrupt payload, so this is compared against
    the reference library rather than a golden string."""
    lzstring = pytest.importorskip("lzstring")
    reference = lzstring.LZString()
    for text in ("", "a", '{"torrents": [{"hash": "abc", "bytes": 1}]}', "á" * 300):
        assert compress_to_encoded_uri_component(text) == (
            reference.compressToEncodedURIComponent(text)
        )
