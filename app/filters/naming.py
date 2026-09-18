import re

import PTT

# Indexers staple their own name onto both ends. PTT reads a trailing one as
# the release group ("... H 265-TROVE [ Seedhive.org ]") and gives up on a
# leading one, so they come off first.
_SITE_TAG = re.compile(r"^\s*(?:\[[^\]]+\]|www\.[\w.-]+)\s*-*\s*|\s*\[[^\]]*\]\s*$")


def _strip_site_tags(name: str) -> str:
    previous = None
    while previous != name:
        previous = name
        name = _SITE_TAG.sub("", name).strip()
    return name


def is_scene_formatted(name: str) -> bool:
    """Whether `name` is well-formed enough for a client to make sense of.

    Approximated by whether a release group can be read off it.

    Accepts  Harbour.Lights.S01.1080p.AMZN.WEB-DL.DDP5.1.H.264.HUN.ENG-QVTX
             Silent Quarry 2023 2160p NF WEB-DL DDP5 1 Atmos DV HDR H 265-TROVE
    Rejects  Nine Tin Soldiers S01-04 + TFB 1080p
             Vasvirag S15 720p
             harbourlights2
    """
    name = _strip_site_tags(name.strip())
    if not name:
        return False
    return PTT.parse_title(name).get("group") is not None
