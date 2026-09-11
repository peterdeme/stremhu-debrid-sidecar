from collections.abc import Callable

from fastapi import Depends, Request

from .. import config as config_module
from ..config import Config
from ..db import Store
from ..debrids.status import DebridStatus
from ..jobs.runner import JobRunner
from .sessions import Sessions
from .templating import Renderer


def singleton[T](value: T) -> Callable[[], T]:
    def provide() -> T:
        return value

    return provide


def config_provider(store: Store) -> Callable[[], Config]:
    def provide() -> Config:
        return config_module.load(store)

    return provide


def renderer_provider(
    store: Store, statuses: DebridStatus, runner: JobRunner
) -> Callable[[Request], Renderer]:
    def provide(request: Request) -> Renderer:
        return Renderer(
            request=request,
            store=store,
            config=config_module.load(store),
            statuses=statuses,
            runner=runner,
        )

    return provide


def auth_dependency(sessions: Sessions):
    from .auth import NotAuthenticated

    def require_auth(request: Request) -> None:
        if not sessions.valid(request.cookies.get("session")):
            raise NotAuthenticated()

    return Depends(require_auth)
