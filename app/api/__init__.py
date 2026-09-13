from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..db import Store
from ..debrids.status import DebridStatus
from ..jobs.runner import JobRunner
from . import auth, middlewares, routes
from .lifespan import get_lifespan
from .sessions import Sessions

__all__ = ["get_lifespan", "install"]

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def install(
    app: FastAPI,
    store: Store,
    sessions: Sessions,
    statuses: DebridStatus,
    runner: JobRunner,
) -> None:
    # Mounted before the routers so the logo loads on the login page too,
    # which is rendered for people who have no session yet.
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    middlewares.install(app)
    app.include_router(auth.get_router(store, sessions))
    app.include_router(routes.get_router(store, sessions, statuses, runner))
