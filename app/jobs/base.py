import logging
import time

from ..config import Config
from ..db import Store
from ..models import JobName, RunResult


class Job:
    name: JobName

    def __init__(self, config: Config, store: Store):
        self.config = config
        self.store = store
        self.log = logging.getLogger(f"app.jobs.{self.name}")

    async def execute(self, result: RunResult) -> None:
        raise NotImplementedError

    async def run(self) -> RunResult:
        result = RunResult(job=self.name)
        self.log.info("job started", extra={"job": self.name})
        try:
            await self.execute(result)
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            self.log.exception("job crashed", extra={"job": self.name})
        result.finished_at = time.time()

        for d in result.decisions:
            self.log.debug(
                "decision",
                extra={
                    "job": self.name,
                    "provider": d.provider,
                    "outcome": d.outcome.value,
                    "info_hash": d.info_hash,
                    "torrent": d.name,
                    "detail": d.detail,
                },
            )

        self.log.info(
            "job finished",
            extra={
                "job": self.name,
                "duration_s": round(result.finished_at - result.started_at, 3),
                "decisions": len(result.decisions),
                "outcomes": {o.value: n for o, n in result.counts.items()},
                "error": result.error,
            },
        )
        return result
