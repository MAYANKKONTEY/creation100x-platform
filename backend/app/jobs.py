"""Audit trail for background operations. Every pipeline run is recorded as a JobRun."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import JobRun, JobStatus


@contextmanager
def run_job(session: Session, name: str, recorder=None) -> Iterator[JobRun]:
    """Record a JobRun. On failure the job is marked failed and committed, then the error re-raised.

    Work done inside the block shares the session; on failure it is rolled back, but the failed
    JobRun and the LLM usage captured by `recorder` are still persisted for the System Logs page.
    """
    job = JobRun(name=name, status=JobStatus.RUNNING, stats={})
    session.add(job)
    session.commit()
    try:
        yield job
    except Exception as e:
        session.rollback()
        if recorder is not None:
            recorder.readd_after_rollback()
        job = session.merge(job)
        job.status = JobStatus.FAILED
        job.error = f"{type(e).__name__}: {e}"[:4000]
        job.finished_at = utcnow()
        session.commit()
        raise
    else:
        job.status = JobStatus.SUCCEEDED
        job.finished_at = utcnow()
        session.commit()
