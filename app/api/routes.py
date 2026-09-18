import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import community_sharing, debrids, jobs, stremhu
from .. import config as config_module
from ..config import Config
from ..db import Store
from ..debrids.status import DebridStatus
from ..jobs.runner import JobRunner
from ..models import JobName, SeedPreference
from . import passwords
from .dependencies import (
    auth_dependency,
    config_provider,
    renderer_provider,
    singleton,
)
from .sessions import Sessions
from .templating import Renderer

_background: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    """asyncio only keeps a weak reference to a running task, so one that is
    not held can be collected mid-await."""
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


def _field(form, name: str) -> str:
    value = form.get(name)
    return value.strip() if isinstance(value, str) else ""


def get_router(
    store: Store, sessions: Sessions, statuses: DebridStatus, runner: JobRunner
) -> APIRouter:
    provide_store = singleton(store)
    provide_statuses = singleton(statuses)
    provide_runner = singleton(runner)
    provide_config = config_provider(store)
    provide_page = renderer_provider(store, statuses, runner)

    router = APIRouter(dependencies=[auth_dependency(sessions)])

    @router.get("/", response_class=HTMLResponse)
    async def overview(page: Annotated[Renderer, Depends(provide_page)]):
        return page.render("overview.html")

    @router.post("/test/stremhu", response_class=HTMLResponse)
    async def test_stremhu(
        page: Annotated[Renderer, Depends(provide_page)],
        stremhu_data_dir: Annotated[str, Form()],
    ):
        return page.render(
            "overview.html",
            test=stremhu.status(Config(stremhu_data_dir=stremhu_data_dir)),
            tested=stremhu_data_dir,
        )

    @router.post("/settings/general")
    async def save_general(
        store: Annotated[Store, Depends(provide_store)],
        config: Annotated[Config, Depends(provide_config)],
        stremhu_data_dir: Annotated[str, Form()],
        ui_password: Annotated[str, Form()] = "",
    ):
        config.stremhu_data_dir = stremhu_data_dir
        config_module.save(store, config)
        if ui_password.strip() and not passwords.env_password():
            store.auth.set_password(*passwords.hash_password(ui_password.strip()))
        return RedirectResponse("/", status_code=303)

    @router.get("/sync", response_class=HTMLResponse)
    async def sync_page(
        page: Annotated[Renderer, Depends(provide_page)],
        store: Annotated[Store, Depends(provide_store)],
        runner: Annotated[JobRunner, Depends(provide_runner)],
    ):
        return page.render(
            "sync.html",
            runs=runner.runs_for(JobName.SYNC_TO_DEBRID),
            pushed=store.debrid.count_pushed(),
        )

    @router.post("/settings/sync")
    async def save_sync(
        request: Request,
        store: Annotated[Store, Depends(provide_store)],
        statuses: Annotated[DebridStatus, Depends(provide_statuses)],
        runner: Annotated[JobRunner, Depends(provide_runner)],
        config: Annotated[Config, Depends(provide_config)],
        push_enabled: Annotated[bool, Form()] = False,
        push_interval_minutes: Annotated[int, Form()] = 15,
        lookback_hours: Annotated[int, Form()] = 48,
        min_fetched_percent: Annotated[float, Form()] = 50,
        require_scene_format: Annotated[bool, Form()] = False,
        seed_preference: Annotated[int, Form()] = SeedPreference.ALWAYS,
    ):
        config.push_enabled = push_enabled
        config.push_interval_minutes = max(1, push_interval_minutes)
        config.lookback_hours = max(1, lookback_hours)
        config.min_fetched_fraction = min(max(min_fetched_percent / 100, 0.0), 1.0)
        config.require_scene_format = require_scene_format
        config.seed_preference = (
            seed_preference
            if seed_preference in set(SeedPreference)
            else SeedPreference.ALWAYS
        )
        config_module.save(store, config)

        form = await request.form()
        supplied = False
        for key in debrids.DEBRIDS:
            value = _field(form, f"{key}_api_key")
            if value:
                supplied = True
            store.debrid.save(key, value or None, enabled=True)

        runner.reschedule()
        if supplied:
            await statuses.refresh(store)

        return RedirectResponse("/sync", status_code=303)

    @router.post("/debrid/{provider}/remove")
    async def remove_debrid(
        provider: str,
        store: Annotated[Store, Depends(provide_store)],
        statuses: Annotated[DebridStatus, Depends(provide_statuses)],
    ):
        if provider in debrids.DEBRIDS:
            store.debrid.delete(provider)
            statuses.forget(provider)
        return RedirectResponse("/sync", status_code=303)

    @router.get("/share", response_class=HTMLResponse)
    async def share_page(
        page: Annotated[Renderer, Depends(provide_page)],
        store: Annotated[Store, Depends(provide_store)],
        runner: Annotated[JobRunner, Depends(provide_runner)],
    ):
        return page.render(
            "share.html",
            runs=runner.runs_for(JobName.PUBLISH_TO_COMMUNITY),
            published=store.community.count_published(),
            last_hashlist=store.community.last_hashlist_url(),
        )

    @router.post("/settings/share")
    async def save_share(
        request: Request,
        store: Annotated[Store, Depends(provide_store)],
        runner: Annotated[JobRunner, Depends(provide_runner)],
        config: Annotated[Config, Depends(provide_config)],
        publish_enabled: Annotated[bool, Form()] = False,
        publish_interval_hours: Annotated[int, Form()] = 24,
    ):
        config.publish_enabled = publish_enabled
        config.publish_interval_hours = max(
            config_module.MIN_PUBLISH_INTERVAL_HOURS, publish_interval_hours
        )
        config_module.save(store, config)

        form = await request.form()
        for key, target in community_sharing.TARGETS.items():
            enabled = bool(form.get(f"{key}_enabled"))
            api_key = _field(form, f"{key}_api_key") if target.needs_key else None
            store.community.save(key, api_key or None, enabled)
        runner.reschedule()
        return RedirectResponse("/share", status_code=303)

    @router.post("/run/{job}")
    async def run_now(job: str, runner: Annotated[JobRunner, Depends(provide_runner)]):
        if jobs.get(job) is None:
            return RedirectResponse("/", status_code=303)
        _spawn(runner.run(job))
        return RedirectResponse(
            "/sync" if job == JobName.SYNC_TO_DEBRID else "/share", status_code=303
        )

    return router
