import pytest
from sqlalchemy import select

from app.config import REPO_ROOT
from app.jobs import run_job
from app.llm.base import Usage
from app.llm.usage import UsageRecorder, estimate_cost
from app.models import JobRun, LLMCall, Source
from app.safety import killswitch


def test_publishing_off_by_default(session):
    assert not killswitch.get_state(session, env_enabled=True).can_publish
    assert not killswitch.get_state(session, env_enabled=False).can_publish


def test_both_flags_required(session):
    killswitch.enable_publishing(session, killswitch.CONFIRM_PHRASE, "ready")
    assert killswitch.get_state(session, env_enabled=True).can_publish
    assert not killswitch.get_state(session, env_enabled=False).can_publish
    with pytest.raises(killswitch.PublishingDisabled):
        killswitch.assert_can_publish(session, env_enabled=False)


def test_enable_requires_exact_phrase(session):
    with pytest.raises(PermissionError):
        killswitch.enable_publishing(session, "yes", "oops")
    assert not killswitch.get_state(session, True).db_enabled


def test_emergency_stop(session):
    killswitch.enable_publishing(session, killswitch.CONFIRM_PHRASE, "ready")
    killswitch.emergency_stop(session, "bad post")
    st = killswitch.get_state(session, True)
    assert not st.can_publish and st.reason == "EMERGENCY STOP: bad post"
    with pytest.raises(killswitch.PublishingDisabled):
        killswitch.assert_can_publish(session, True)


def test_estimate_cost():
    pricing = {"claude-opus-5-5": {"input": 4.0, "output": 20.0}}
    u = Usage(purpose="x", model="claude-opus-5-5", input_tokens=1_000_000, output_tokens=100_000)
    assert estimate_cost(u, pricing) == 6.0
    assert estimate_cost(Usage(purpose="x", model="unknown"), pricing) is None


def test_job_success(session):
    with run_job(session, "demo") as job:
        job.stats = {"n": 1}
    row = session.get(JobRun, job.id)
    assert row.status == "succeeded" and row.finished_at is not None and row.stats == {"n": 1}


def test_failed_job_rolls_back_work_but_keeps_job_and_llm_usage(session):
    recorder = UsageRecorder(session, REPO_ROOT / "config" / "pricing.yaml")
    with pytest.raises(RuntimeError):
        with run_job(session, "demo", recorder=recorder):
            session.add(Source(name="should-vanish", kind="rss", url="https://x.test"))
            recorder(Usage(purpose="research.gather", model="claude-opus-5-5", input_tokens=500, output_tokens=50))
            session.flush()
            raise RuntimeError("kaboom")
    assert session.scalar(select(Source).where(Source.name == "should-vanish")) is None
    job = session.scalar(select(JobRun).where(JobRun.name == "demo"))
    assert job.status == "failed" and "kaboom" in job.error
    calls = session.scalars(select(LLMCall)).all()
    assert len(calls) == 1 and calls[0].est_cost_usd == pytest.approx(0.003)
