from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..db import Store
from ..jobs.runner import JobRunner
from .auth import ensure_admin_password


def get_lifespan(store: Store, runner: JobRunner):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ensure_admin_password(store)
        runner.start()
        yield
        runner.stop()
        store.conn.close()

    return lifespan
