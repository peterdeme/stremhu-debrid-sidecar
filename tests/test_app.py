"""Eleven tests, picked by what has actually broken rather than by coverage."""

import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from app import config as config_module
from app import db, filters, stremhu
from app.debrids.torbox import Torbox
from app.filters import Marker
from app.jobs.sync_to_debrid import SyncToDebridJob
from app.lzstring import compress_to_encoded_uri_component
from app.models import JobName, Outcome

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
            "require_scene_format": "true",
            "require_language_tag": "true",
            "seed_preference": "3",
            "remove_inactive": "true",
        },
    )
    cfg = config_module.load(store)
    assert (cfg.push_interval_minutes, cfg.lookback_hours) == (25, 72)
    assert cfg.min_fetched_fraction == 0.4
    assert cfg.require_scene_format is True
    assert cfg.require_language_tag is True
    assert cfg.require_resolution is False
    assert cfg.remove_inactive is True
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
    assert {
        "settings",
        "admin_credentials",
        "debrids",
        "sharing",
        "pushed",
        "published",
        "runs",
        "decisions",
    } <= tables


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


def test_rejected_names_stay_out_of_the_next_query(tmp_path, store):
    """Every run used to fetch, decode and reject the same badly named
    torrents, and they filled the playback limit. Switching the filter off has
    to bring them back, or the setting would only ever apply to new plays."""
    db_path = tmp_path / "app.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        create table playback_histories (
            indexer_id text, torrent_id text, created_at text, torrent_name text,
            file_name text, file_index integer, imdb_info text
        );
        create table torrent_files (
            indexer_id text, torrent_id text, info_hash text, torrent_bytes blob
        );
        """
    )
    for i, name in enumerate(["Some Show S01", "Good.Show.S01.1080p.WEB-DL-GRP"]):
        conn.execute(
            "insert into playback_histories values (?, ?, '2026-01-01', ?, '', 0, null)",
            ("idx", str(i), name),
        )
        conn.execute(
            "insert into torrent_files values (?, ?, ?, x'00')",
            ("idx", str(i), f"{i:040X}"),
        )
    conn.commit()
    conn.close()
    conn = stremhu.connect(db_path)

    bad = f"{0:040x}"
    run_id = store.runs.start(JobName.SYNC_TO_DEBRID, 0)
    store.runs.finish(
        run_id,
        1,
        None,
        [("Some Show S01", bad, Outcome.NOT_SCENE_FORMAT.value, "", "torbox")],
    )

    def names(**settings):
        store.config.save(settings)
        job = SyncToDebridJob(config_module.load(store), store)
        excluded = store.runs.hashes_with_outcome(job._final_rejections)
        return {
            p.torrent_name for p in stremhu.recent_playbacks(conn, exclude=excluded)
        }

    assert names(require_scene_format=True) == {"Good.Show.S01.1080p.WEB-DL-GRP"}
    assert names(require_scene_format=False, require_resolution=True) == {
        "Some Show S01",
        "Good.Show.S01.1080p.WEB-DL-GRP",
    }


def test_only_dead_downloads_count_as_inactive():
    """This list gets deleted, so it has to be exactly what TorBox's UI calls
    inactive. Going by the `active` flag alone picked 563 of 568 downloads on a
    real account: every cached one has it off too."""

    def reply(request):
        if request.url.path.endswith("/torrents/mylist"):
            states = [
                ("expired", False),
                ("incomplete", False),
                ("reported missing", False),
                ("cached", False),
                ("completed", False),
                ("uploading (no peers)", False),
                ("uploading", True),
                ("some state torbox adds later", False),
            ]
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": i,
                            "hash": f"{i:040x}",
                            "name": state,
                            "download_state": state,
                            "active": active,
                        }
                        for i, (state, active) in enumerate(states, start=1)
                    ]
                },
            )
        removed.append(json.loads(request.content))
        return httpx.Response(200, json={"success": True})

    async def run():
        async with Torbox("key") as client:
            client._client = httpx.AsyncClient(
                base_url="https://torbox.test", transport=httpx.MockTransport(reply)
            )
            dead = await client.inactive_torrents()
            await client.remove_torrent(dead[0].id)
            return dead

    removed: list[dict] = []
    dead = asyncio.run(run())
    assert [t.state for t in dead] == ["expired", "incomplete", "reported missing"]
    assert removed == [{"torrent_id": 1, "operation": "delete"}]


def test_lzstring_matches_the_reference_implementation():
    """DMM would happily accept a corrupt payload, so this is compared against
    the reference library rather than a golden string."""
    lzstring = pytest.importorskip("lzstring")
    reference = lzstring.LZString()
    for text in ("", "a", '{"torrents": [{"hash": "abc", "bytes": 1}]}', "á" * 300):
        assert compress_to_encoded_uri_component(text) == (
            reference.compressToEncodedURIComponent(text)
        )


CORPUS = Path(__file__).parent / "data" / "torrent_names.txt"


def _corpus():
    for line in CORPUS.read_text().splitlines():
        if line.startswith(("+ ", "- ")):
            yield line[2:], line[0] == "+"


@pytest.mark.parametrize("name, expected", list(_corpus()), ids=lambda v: None)
def test_scene_format_detection(name, expected):
    """One case per naming shape a real run throws at this. The first version
    of the filter looked right on a handful of invented examples and then threw
    away half of an actual run - every well-formed release whose dots had been
    flattened to spaces somewhere upstream - so the shapes are what matter, and
    the names carrying them are made up."""
    assert filters.is_scene_formatted(name) is expected


def test_a_well_formed_name_can_still_be_missing_what_matters():
    """The reason the group check alone was not enough: scene releases turn up
    with the resolution or the language left off the name, and downstream that
    is the same as not having them, so the cache lookup never matches."""
    name = "Harbour.Lights.S01E04.WEB-DL.DDP5.1.H.264-QVTX"
    everything = {Marker.GROUP, Marker.RESOLUTION, Marker.LANGUAGE}

    assert filters.is_scene_formatted(name)
    assert filters.missing_markers(name, everything) == {
        Marker.RESOLUTION,
        Marker.LANGUAGE,
    }
    assert filters.missing_markers(name, {Marker.GROUP}) == set()
    assert filters.missing_markers(name, set()) == set()
    assert (
        filters.missing_markers(
            "Harbour.Lights.S01.1080p.AMZN.WEB-DL.DDP5.1.H.264.HUN.ENG-QVTX", everything
        )
        == set()
    )


def test_site_tags_do_not_hide_the_release_group():
    """Indexers staple their name onto both ends, and a trailing one reads as
    the release group, which is how five good releases got rejected."""
    assert filters.is_scene_formatted(
        "Silent Quarry S01E01 A Quiet Road 2160p WEB-DL DDP5 1 Atmos H 265-TROVE [ Seedhive.org ]"
    )
    assert filters.is_scene_formatted(
        "[Torrindex.to] The.Rusty.Gate.2016.2160p.BluRay.x265.10bit.HDR.TrueHD.7.1.Atmos-NULLCAST"
    )
    assert not filters.is_scene_formatted("")
