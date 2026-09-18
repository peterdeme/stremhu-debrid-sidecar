import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .. import community_sharing, debrids, stremhu
from .. import config as config_module
from ..config import Config
from ..db import Store
from ..debrids.status import DebridStatus
from ..jobs.runner import JobRunner
from ..models import JobName, Outcome
from . import passwords

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)

REPO_URL = "https://github.com/peterdeme/stremhu-debrid-sidecar"

COMPOSE_EXAMPLE = """services:
  stremhu-source:
    image: s4pp1/stremhu-source:latest
    ports:
      - "6881:6881"
    volumes:
      - ./stremhu-data:/app/data

  stremhu-debrid-sidecar:
    image: ghcr.io/peterdeme/stremhu-debrid-sidecar:latest
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./sidecar-data:/data
      - ./stremhu-data/system/database:/stremhu/system/database
      - ./stremhu-data/downloads:/stremhu/downloads:ro
"""
PUBLISH_PAYLOAD_URL = f"{REPO_URL}/blob/main/app/community_sharing/dmm.py"

OUTCOME_LABELS = {
    Outcome.PUSHED: "feltöltve",
    Outcome.ALREADY_CACHED: "feltöltve (már megvolt)",
    Outcome.ALREADY_PUSHED: "korábban feltöltve",
    Outcome.TOO_BIG: "túl nagy",
    Outcome.BARELY_WATCHED: "alig nézted",
    Outcome.NOT_SCENE_FORMAT: "nem scene formátumú",
    Outcome.NO_FILE: "a stremhu törölte a fájlt",
    Outcome.NO_TORRENT: "a .torrent már nincs meg",
    Outcome.HASH_MISMATCH: "hash eltérés",
    Outcome.FAILED: "sikertelen",
}
OUTCOME_SENTENCES = {
    Outcome.PUSHED: "sikeresen feltöltve",
    Outcome.ALREADY_CACHED: "sikeresen feltöltve (már cached volt)",
    Outcome.ALREADY_PUSHED: "korábban már feltöltve",
    Outcome.TOO_BIG: "túl nagy, nem került feltöltésre",
    Outcome.BARELY_WATCHED: "alig nézted, nem került feltöltésre",
    Outcome.NOT_SCENE_FORMAT: "nem scene formátumú, nem került feltöltésre",
    Outcome.NO_FILE: "a stremhu már törölte a fájlt",
    Outcome.NO_TORRENT: "a .torrent már nincs meg, nem került feltöltésre",
    Outcome.HASH_MISMATCH: "hash eltérés, nem került feltöltésre",
    Outcome.FAILED: "sikertelen feltöltés",
}
GOOD = {Outcome.PUSHED, Outcome.ALREADY_CACHED}
BAD = {Outcome.FAILED, Outcome.HASH_MISMATCH}


def relative_time(ts: float) -> str:
    seconds = max(0, int(time.time() - ts))
    if seconds < 60:
        return "épp most"
    if seconds < 3600:
        return f"{seconds // 60} perce"
    if seconds < 86400:
        return f"{seconds // 3600} órája"
    return f"{seconds // 86400} napja"


templates.env.globals["outcome_label"] = lambda o: OUTCOME_LABELS.get(o, o.value)
templates.env.globals["outcome_sentence"] = lambda o: OUTCOME_SENTENCES.get(o, o.value)
templates.env.globals["outcome_tone"] = lambda o: (
    "good" if o in GOOD else ("bad" if o in BAD else "muted")
)
templates.env.filters["relative_time"] = relative_time
templates.env.globals["Outcome"] = Outcome
templates.env.globals["JobName"] = JobName
templates.env.globals["REPO_URL"] = REPO_URL
templates.env.globals["COMPOSE_EXAMPLE"] = COMPOSE_EXAMPLE
templates.env.globals["PUBLISH_PAYLOAD_URL"] = PUBLISH_PAYLOAD_URL


@dataclass
class Renderer:
    request: Request
    store: Store
    config: Config
    statuses: DebridStatus
    runner: JobRunner

    def render(self, template: str, **extra):
        context = {
            "cfg": self.config,
            "stremhu": stremhu.status(self.config),
            "running": sorted(self.runner.running),
            "min_publish_hours": config_module.MIN_PUBLISH_INTERVAL_HOURS,
            "env_password": passwords.env_password() is not None,
            "debrid_status": self.statuses.all(),
            "providers": debrids.DEBRIDS,
            "sharing_targets": community_sharing.TARGETS,
            "configured": {
                r.provider: r for r in self.store.debrid.all(enabled_only=False)
            },
            "configured_sharing": {
                r.provider: r for r in self.store.community.all(enabled_only=False)
            },
        }
        context.update(extra)
        return templates.TemplateResponse(self.request, template, context)
