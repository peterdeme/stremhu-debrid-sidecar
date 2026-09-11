import sqlite3

from ..models import Decision, JobName, Outcome, RunResult


class RunStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def start(self, job: JobName, started_at: float) -> int:
        with self.conn:
            cur = self.conn.execute(
                "insert into runs (job, started_at) values (?, ?)", (job, started_at)
            )
        if cur.lastrowid is None:
            raise RuntimeError("run row was not created")
        return cur.lastrowid

    def finish(
        self,
        run_id: int,
        finished_at: float,
        error: str | None,
        decisions: list[tuple[str, str, str, str, str | None]],
    ) -> None:
        with self.conn:
            self.conn.execute(
                "update runs set finished_at = ?, error = ? where id = ?",
                (finished_at, error, run_id),
            )
            self.conn.executemany(
                "insert into decisions (run_id, name, info_hash, outcome, detail, provider)"
                " values (?, ?, ?, ?, ?, ?)",
                [(run_id, *d) for d in decisions],
            )

    def history(self, job: JobName | None = None, limit: int = 25) -> list[RunResult]:
        sql = "select * from runs"
        params: list = []
        if job:
            sql += " where job = ?"
            params.append(job)
        sql += " order by started_at desc limit ?"
        params.append(limit)

        return [
            RunResult(
                job=JobName(row["job"]),
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                error=row["error"],
                decisions=self._decisions(row["id"]),
            )
            for row in self.conn.execute(sql, params)
        ]

    def _decisions(self, run_id: int) -> list[Decision]:
        return [
            Decision(
                name=d["name"] or "",
                info_hash=d["info_hash"] or "",
                outcome=Outcome(d["outcome"]),
                detail=d["detail"] or "",
                provider=d["provider"],
            )
            for d in self.conn.execute(
                "select * from decisions where run_id = ?", (run_id,)
            )
        ]

    def prune(self, keep: int = 500) -> int:
        with self.conn:
            cur = self.conn.execute(
                "delete from runs where id not in"
                " (select id from runs order by started_at desc limit ?)",
                (keep,),
            )
        return cur.rowcount
