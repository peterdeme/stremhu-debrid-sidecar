import time

from ..config import Config
from ..db import Store
from ..models import JobName, RunResult


class Job:
    name: JobName

    def __init__(self, config: Config, store: Store):
        self.config = config
        self.store = store

    async def execute(self, result: RunResult) -> None:
        raise NotImplementedError

    async def run(self) -> RunResult:
        result = RunResult(job=self.name)
        try:
            await self.execute(result)
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
        result.finished_at = time.time()
        return result
