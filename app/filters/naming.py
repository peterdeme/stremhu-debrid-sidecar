import re
from collections.abc import Iterable
from enum import StrEnum

import PTT

# Indexers staple their own name onto both ends. PTT reads a trailing one as
# the release group ("... H 265-TROVE [ Seedhive.org ]") and gives up on a
# leading one, so they come off first.
_SITE_TAG = re.compile(r"^\s*(?:\[[^\]]+\]|www\.[\w.-]+)\s*-*\s*|\s*\[[^\]]*\]\s*$")


class Marker(StrEnum):
    GROUP = "group"
    RESOLUTION = "resolution"
    LANGUAGE = "language"


def _strip_site_tags(name: str) -> str:
    previous = None
    while previous != name:
        previous = name
        name = _SITE_TAG.sub("", name).strip()
    return name


def missing_markers(name: str, required: Iterable[Marker]) -> set[Marker]:
    """Which of `required` cannot be read off `name`.

    A release can be perfectly well formed and still be useless downstream:
    without a resolution or a language tag the scrapers file it under unknown,
    so nobody looking for a 1080p HUN copy will ever be served it.

    Missing nothing  Harbour.Lights.S01.1080p.AMZN.WEB-DL.DDP5.1.H.264.HUN.ENG-QVTX
    Missing group    Vasvirag S15 720p
    Missing the rest Harbour.Lights.S01E04.WEB-DL.DDP5.1.H.264-QVTX
    """
    required = set(required)
    if not required:
        return set()

    name = _strip_site_tags(name.strip())
    if not name:
        return required

    parsed = PTT.parse_title(name)
    present = {
        marker
        for marker, key in (
            (Marker.GROUP, "group"),
            (Marker.RESOLUTION, "resolution"),
            (Marker.LANGUAGE, "languages"),
        )
        if parsed.get(key)
    }
    return required - present


def is_scene_formatted(name: str) -> bool:
    """Whether `name` is well-formed enough for a client to make sense of.

    Approximated by whether a release group can be read off it.

    Accepts  Harbour.Lights.S01.1080p.AMZN.WEB-DL.DDP5.1.H.264.HUN.ENG-QVTX
             Silent Quarry 2023 2160p NF WEB-DL DDP5 1 Atmos DV HDR H 265-TROVE
    Rejects  Nine Tin Soldiers S01-04 + TFB 1080p
             Vasvirag S15 720p
             harbourlights2
    """
    return not missing_markers(name, {Marker.GROUP})
