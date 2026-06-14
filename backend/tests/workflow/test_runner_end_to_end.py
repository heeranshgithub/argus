"""End-to-end runner test — full graph against fakes, asserting DB state."""

from mongomock_motor import AsyncMongoMockClient

from app.models.session import SessionCreate, SessionStatus
from app.models.workflow import EventKind, NodeStatus, RunStatus
from app.repositories import report_repo, session_repo, workflow_repo
from app.workflow.deps import WorkflowDeps
from app.workflow.runner import WorkflowRunner
from tests.workflow.conftest import FakeFetcher, FakeSearchClient, happy_path_llm

_NINE_SECTIONS = {
    "company_overview",
    "products_and_services",
    "target_customers",
    "business_signals",
    "risks_and_challenges",
    "suggested_discovery_questions",
    "suggested_outreach_strategy",
    "unknowns",
    "sources",
}


async def _make_session(db) -> str:
    session = await session_repo.create(
        db,
        SessionCreate(
            company_name="Acme",
            website="https://example.com",
            objective="Explore an expansion partnership.",
        ),
    )
    return session.id


async def test_runner_runs_full_workflow_and_persists_everything(settings) -> None:
    db = AsyncMongoMockClient(tz_aware=True)["argus_test"]
    session_id = await _make_session(db)
    deps = WorkflowDeps(
        llm=happy_path_llm(), search=FakeSearchClient(), fetcher=FakeFetcher(), settings=settings
    )
    runner = WorkflowRunner(db, deps)

    run_id = await runner.start(session_id)
    await runner.execute(run_id, session_id)

    # --- session transitioned created → running → completed -------------------
    session = await session_repo.get(db, session_id)
    assert session.status is SessionStatus.COMPLETED

    # --- run captured the full event timeline ---------------------------------
    run = await workflow_repo.get_run(db, run_id)
    assert run.status is RunStatus.COMPLETED
    assert run.finished_at is not None
    kinds = [e.kind for e in run.events]
    assert kinds[0] is EventKind.RUN_STARTED
    assert kinds[-1] is EventKind.RUN_COMPLETED
    # Every node started and finished, in order.
    started = [e.node for e in run.events if e.kind is EventKind.NODE_STARTED]
    assert started == [
        "planner",
        "researcher",
        "signal_extractor",
        "analyst",
        "quality_check",
        "reporter",
    ]
    assert all(s is NodeStatus.DONE for s in run.node_status.values())

    # --- report document has all nine sections --------------------------------
    report = await report_repo.get_by_session(db, session_id)
    assert report is not None
    dumped = report.model_dump()
    assert set(dumped) >= _NINE_SECTIONS
    assert report.company_overview
    assert report.sources


async def test_runner_marks_failed_on_unexpected_error(settings) -> None:
    db = AsyncMongoMockClient(tz_aware=True)["argus_test"]
    session_id = await _make_session(db)

    class BoomLLM:
        async def complete(self, *a, **k):
            raise RuntimeError("kaboom")

    deps = WorkflowDeps(
        llm=BoomLLM(), search=FakeSearchClient(), fetcher=FakeFetcher(), settings=settings
    )
    runner = WorkflowRunner(db, deps)
    run_id = await runner.start(session_id)
    await runner.execute(run_id, session_id)

    run = await workflow_repo.get_run(db, run_id)
    assert run.status is RunStatus.FAILED
    assert run.error is not None
    assert run.error.message
    session = await session_repo.get(db, session_id)
    assert session.status is SessionStatus.FAILED


async def test_runner_resume_after_failure_completes(settings) -> None:
    """A failed run resumes from checkpoint and reaches completion."""
    db = AsyncMongoMockClient(tz_aware=True)["argus_test"]
    session_id = await _make_session(db)

    # The planner blows up on the first attempt, failing the whole run.
    mode = {"fail": True}
    llm = happy_path_llm()
    base_complete = llm.complete

    async def maybe_fail(system, user, *, response_model=None, **kwargs):
        if (
            mode["fail"]
            and response_model is not None
            and response_model.__name__ == "PlanResult"
        ):
            raise RuntimeError("planner down")
        return await base_complete(system, user, response_model=response_model, **kwargs)

    llm.complete = maybe_fail  # type: ignore[method-assign]
    deps = WorkflowDeps(
        llm=llm, search=FakeSearchClient(), fetcher=FakeFetcher(), settings=settings
    )
    runner = WorkflowRunner(db, deps)

    run_id = await runner.start(session_id)
    await runner.execute(run_id, session_id)
    failed = await workflow_repo.get_run(db, run_id)
    assert failed.status is RunStatus.FAILED

    # Heal the planner and resume: a new run continues and finishes the report.
    mode["fail"] = False
    deps.llm = happy_path_llm()
    resume_run_id = await runner.resume(session_id)
    await runner.execute(resume_run_id, session_id, resume=True)

    resumed = await workflow_repo.get_run(db, resume_run_id)
    assert resumed.status is RunStatus.COMPLETED
    report = await report_repo.get_by_session(db, session_id)
    assert report is not None
