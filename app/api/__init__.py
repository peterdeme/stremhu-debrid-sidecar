from fastapi import FastAPI

from ..db import Store
from ..debrids.status import DebridStatus
from ..jobs.runner import JobRunner
from . import auth, middlewares, routes
from .lifespan import get_lifespan
from .sessions import Sessions

__all__ = ["get_lifespan", "install"]


def install(
    app: FastAPI,
    store: Store,
    sessions: Sessions,
    statuses: DebridStatus,
    runner: JobRunner,
) -> None:
    middlewares.install(app)
    app.include_router(auth.get_router(store, sessions))
    app.include_router(routes.get_router(store, sessions, statuses, runner))
