import logging
import time
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import load as load_config
from ..db import Store
from ..debrids.status import DebridStatus
from ..models import JobName, Outcome, RunResult
from . import get

MAX_RUNS_KEPT = 25

# A torrent that was already cached still lands in the debrid library, so it
# counts as an upload as far as the run list is concerned.
UPLOAD_OUTCOMES = (Outcome.PUSHED, Outcome.ALREADY_CACHED)

# How long an overdue job waits after (re)scheduling. Long enough for the app
# to finish starting, and to untick a box that was saved by mistake.
OVERDUE_DELAY = timedelta(minutes=2)


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

    def runs_for(self, job: JobName, only_uploads: bool = False) -> list[RunResult]:
        outcomes = UPLOAD_OUTCOMES if only_uploads else ()
        return self.store.runs.history(job, MAX_RUNS_KEPT, with_outcomes=outcomes)

    def next_run(self, job: JobName) -> float | None:
        scheduled = self.scheduler.get_job(job)
        # Jobs added before the scheduler starts are pending and have no
        # next_run_time yet, hence the getattr.
        when = getattr(scheduled, "next_run_time", None)
        return when.timestamp() if when else None

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

    def _next_due(self, job: JobName, interval: timedelta) -> datetime:
        """When a job is next due, counted from its last run.

        An interval trigger on its own counts from the moment it's scheduled,
        which is every startup and every settings save. A container restarted
        more often than the interval would then never run the job at all.
        """
        soonest = datetime.now(UTC) + OVERDUE_DELAY
        last = self.store.runs.last_started(job)
        if last is None:
            return soonest
        return max(soonest, datetime.fromtimestamp(last, UTC) + interval)

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
            self._schedule(
                JobName.SYNC_TO_DEBRID,
                timedelta(minutes=config.push_interval_minutes),
            )
        if config.publish_enabled:
            self._schedule(
                JobName.PUBLISH_TO_COMMUNITY,
                timedelta(hours=config.effective_publish_interval_hours),
            )

    def _schedule(self, job: JobName, interval: timedelta) -> None:
        self.scheduler.add_job(
            self.run,
            IntervalTrigger(seconds=interval.total_seconds()),
            args=[job],
            id=job,
            name=job,
            max_instances=1,
            coalesce=True,
            next_run_time=self._next_due(job, interval),
        )
