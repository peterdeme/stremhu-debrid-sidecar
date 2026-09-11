import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from . import api, db
from .api.sessions import Sessions
from .debrids.status import DebridStatus
from .jobs.runner import JobRunner

conn = db.connect()
version = db.migrate(conn)
store = db.Store(conn)
print(f"database ready at schema version {version}")

sessions = Sessions()
statuses = DebridStatus()
runner = JobRunner(AsyncIOScheduler(), store, statuses)

app = FastAPI(title="stremhu debrid sidecar", lifespan=api.get_lifespan(store, runner))
api.install(app, store, sessions, statuses, runner)


@app.get("/healthz")
async def healthz():
    return {"ok": True, "time": time.time()}
