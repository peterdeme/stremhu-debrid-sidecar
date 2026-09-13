from ..models import JobName
from .base import Job
from .publish_to_community import PublishToCommunityJob
from .sync_to_debrid import SyncToDebridJob

__all__ = ["JOBS", "Job", "PublishToCommunityJob", "SyncToDebridJob", "get"]

JOBS: dict[JobName, type[Job]] = {
    SyncToDebridJob.name: SyncToDebridJob,
    PublishToCommunityJob.name: PublishToCommunityJob,
}


def get(name: str) -> type[Job] | None:
    try:
        return JOBS[JobName(name)]
    except KeyError, ValueError:
        return None
