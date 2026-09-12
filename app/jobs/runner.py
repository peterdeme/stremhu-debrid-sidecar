import logging
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import load as load_config
from ..db import Store
from ..debrids.status import DebridStatus
from ..models import JobName, RunResult
from . import get

MAX_RUNS_KEPT = 25


class JobRunner:
    def __init__(
        self, scheduler: AsyncIOScheduler, store: Store, statuses: DebridStatus
    ):
        self.scheduler = scheduler
        self.store = store
        self.statuses = statuses
        self.running: set[str] = set()
        self.log = logging.getLogger(__name__)

    def start(self) -> None:
        self.reschedule()
        self.scheduler.start()
        self.log.info("scheduler started")

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        self.log.info("scheduler stopped")

    def runs_for(self, job: JobName) -> list[RunResult]:
        return self.store.runs.history(job, MAX_RUNS_KEPT)

    async def run(self, name: str) -> RunResult | None:
        job = get(name)
        if job is None:
            self.log.warning("unknown job requested", extra={"job": name})
            return None
        if name in self.running:
            self.log.info("job already running, skipping", extra={"job": name})
            return None
        self.running.add(name)
        try:
            result = await job(load_config(self.store), self.store).run()
            for provider, account in (result.accounts or {}).items():
                self.statuses.record(provider, account)
            run_id = self.store.runs.start(result.job, result.started_at)
            self.store.runs.finish(
                run_id,
                result.finished_at or time.time(),
                result.error,
                [
                    (d.name, d.info_hash, d.outcome.value, d.detail, d.provider)
                    for d in result.decisions
                ],
            )
            self.store.runs.prune()
            return result
        finally:
            self.running.discard(name)

    def reschedule(self) -> None:
        config = load_config(self.store)
        self.scheduler.remove_all_jobs()
        self.log.info(
            "scheduling jobs",
            extra={
                "push_enabled": config.push_enabled,
                "push_interval_minutes": config.push_interval_minutes,
                "publish_enabled": config.publish_enabled,
                "publish_interval_hours": config.effective_publish_interval_hours,
            },
        )
        if config.push_enabled:
            self.scheduler.add_job(
                self.run,
                IntervalTrigger(minutes=config.push_interval_minutes),
                args=[JobName.SYNC_TO_DEBRID],
                id=JobName.SYNC_TO_DEBRID,
                max_instances=1,
                coalesce=True,
            )
        if config.publish_enabled:
            self.scheduler.add_job(
                self.run,
                IntervalTrigger(hours=config.effective_publish_interval_hours),
                args=[JobName.PUBLISH_TO_COMMUNITY],
                id=JobName.PUBLISH_TO_COMMUNITY,
                max_instances=1,
                coalesce=True,
            )
