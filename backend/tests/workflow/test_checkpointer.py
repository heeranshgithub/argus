"""Mongo checkpointer tests — round-trip, listing, and resume-after-crash."""

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.repositories import workflow_repo
from app.workflow.checkpointer import MongoCheckpointer
from app.workflow.deps import WorkflowDeps
from app.workflow.events import RunContext, bind_run_context
from app.workflow.graph import build_graph
from app.workflow.tools.llm import FakeLLMClient
from tests.workflow.conftest import (
    FakeFetcher,
    FakeSearchClient,
    happy_path_llm,
    make_analysis,
    make_plan,
    make_quality,
    make_report,
    make_signals,
)


def _initial_state(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "run_id": "run-x",
        "company_name": "Acme",
        "website": "https://example.com",
        "objective": "Explore an expansion partnership.",
        "research_iteration": 0,
    }


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}, "recursion_limit": 30}


async def _run(graph, db, session_id, state):
    run_id = await workflow_repo.create_run(db, session_id)
    async with bind_run_context(RunContext(db=db, run_id=run_id, session_id=session_id)):
        return await graph.ainvoke(state, config=_config(session_id))


async def test_checkpointer_roundtrips_and_lists(settings) -> None:
    db = AsyncMongoMockClient(tz_aware=True)["argus_test"]
    deps = WorkflowDeps(
        llm=happy_path_llm(), search=FakeSearchClient(), fetcher=FakeFetcher(), settings=settings
    )
    checkpointer = MongoCheckpointer(db)
    graph = build_graph(deps, checkpointer=checkpointer)

    await _run(graph, db, "sess-cp", _initial_state("sess-cp"))

    # The latest checkpoint holds the finished state (with the report).
    tup = await checkpointer.aget_tuple(_config("sess-cp"))
    assert tup is not None
    assert "report" in tup.checkpoint["channel_values"]

    # Multiple checkpoints were written across the run's super-steps.
    seen = [t async for t in checkpointer.alist(_config("sess-cp"))]
    assert len(seen) > 1


class _CrashingLLM(FakeLLMClient):
    """Happy-path LLM that raises the first time the analyst is called."""

    def __init__(self) -> None:
        super().__init__(
            {
                "PlanResult": [make_plan()],
                "SignalsResult": [make_signals()],
                "AnalysisResult": [make_analysis()],
                "QualityResult": [make_quality()],
                "ReportDraft": [make_report()],
            }
        )
        self._analyst_calls = 0

    async def complete(self, system, user, *, response_model=None, **kwargs):
        if response_model is not None and response_model.__name__ == "AnalysisResult":
            self._analyst_calls += 1
            if self._analyst_calls == 1:
                raise RuntimeError("analyst exploded")
        return await super().complete(system, user, response_model=response_model, **kwargs)


async def test_resume_continues_from_checkpoint_without_rerunning(settings) -> None:
    db = AsyncMongoMockClient(tz_aware=True)["argus_test"]
    checkpointer = MongoCheckpointer(db)
    session_id = "sess-resume"

    # --- first attempt: crashes in the analyst node ---------------------------
    search = FakeSearchClient()
    deps1 = WorkflowDeps(
        llm=_CrashingLLM(), search=search, fetcher=FakeFetcher(), settings=settings
    )
    graph1 = build_graph(deps1, checkpointer=checkpointer)
    with pytest.raises(Exception):  # noqa: B017 - LangGraph may wrap the error
        await _run(graph1, db, session_id, _initial_state(session_id))

    searches_before = len(search.calls)
    assert searches_before > 0  # researcher had run before the crash

    # A checkpoint survived the crash (state up to signal_extractor).
    tup = await checkpointer.aget_tuple(_config(session_id))
    assert tup is not None
    assert "extracted_signals" in tup.checkpoint["channel_values"]
    assert "report" not in tup.checkpoint["channel_values"]

    # --- resume with a fresh, healthy runner ----------------------------------
    fresh_llm = FakeLLMClient(
        {
            "PlanResult": [make_plan()],
            "SignalsResult": [make_signals()],
            "AnalysisResult": [make_analysis()],
            "QualityResult": [make_quality()],
            "ReportDraft": [make_report()],
        }
    )
    deps2 = WorkflowDeps(
        llm=fresh_llm, search=search, fetcher=FakeFetcher(), settings=settings
    )
    graph2 = build_graph(deps2, checkpointer=checkpointer)
    final = await _run(graph2, db, session_id, None)  # None → resume

    assert "report" in final
    # Researcher did NOT run again (no new searches on the shared client).
    assert len(search.calls) == searches_before
    # Earlier nodes were not re-executed: only analyst→quality→reporter ran.
    called_models = {c["response_model"] for c in fresh_llm.calls}
    assert "PlanResult" not in called_models
    assert "SignalsResult" not in called_models
    assert {"AnalysisResult", "QualityResult", "ReportDraft"} <= called_models
