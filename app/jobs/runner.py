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

    def start(self) -> None:
        self.reschedule()
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)

    def runs_for(self, job: JobName) -> list[RunResult]:
        return self.store.runs.history(job, MAX_RUNS_KEPT)

    async def run(self, name: str) -> RunResult | None:
        job = get(name)
        if job is None or name in self.running:
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
