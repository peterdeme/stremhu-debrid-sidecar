import logging
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from . import api, db, logs
from .api.sessions import Sessions
from .debrids.status import DebridStatus
from .jobs.runner import JobRunner

logs.configure()
log = logging.getLogger(__name__)

conn = db.connect()
version = db.migrate(conn)
store = db.Store(conn)
log.info("database ready", extra={"schema_version": version})

sessions = Sessions()
statuses = DebridStatus()
runner = JobRunner(AsyncIOScheduler(), store, statuses)

app = FastAPI(title="stremhu debrid sidecar", lifespan=api.get_lifespan(store, runner))
api.install(app, store, sessions, statuses, runner)


@app.get("/healthz")
async def healthz():
    return {"ok": True, "time": time.time()}
