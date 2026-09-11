import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from starlette.testclient import TestClient

from app import api, db
from app.api import passwords
from app.api.sessions import Sessions
from app.debrids.status import DebridStatus
from app.jobs.runner import JobRunner

PASSWORD = "test-password"


@pytest.fixture
def store(tmp_path):
    conn = db.connect(tmp_path / "sidecar.db")
    db.migrate(conn)
    return db.Store(conn)


@pytest.fixture
def app(store):
    """The app assembled the way main.py assembles it, minus the lifespan.

    Built per test against tmp_path, so nothing leaks between them and no
    environment variable has to be juggled to keep the real database out.
    """
    store.auth.set_password(*passwords.hash_password(PASSWORD))
    fastapi_app = FastAPI()
    api.install(
        fastapi_app,
        store,
        Sessions(),
        DebridStatus(),
        JobRunner(AsyncIOScheduler(), store, DebridStatus()),
    )
    return fastapi_app


@pytest.fixture
def anonymous(app):
    return TestClient(app)


@pytest.fixture
def client(anonymous):
    r = anonymous.post("/login", data={"password": PASSWORD})
    assert r.status_code == 200, "login should land on the overview page"
    return anonymous
