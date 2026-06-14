"""Planner node tests — initial plan and gap-closing follow-up plan."""

from app.models.workflow import EventKind
from app.repositories import workflow_repo
from app.workflow.nodes.planner import build_planner
from app.workflow.tools.llm import FakeLLMClient
from tests.workflow.conftest import base_state, invoke_node, make_plan


async def test_planner_produces_plan_and_emits_events(deps, db) -> None:
    node = build_planner(deps)
    update, run_id = await invoke_node(node, base_state(), db)

    plan = update["plan"]
    assert len(plan) == 5
    assert plan[0]["id"] == "q0"
    assert all({"id", "question", "rationale"} <= set(q) for q in plan)

    run = await workflow_repo.get_run(db, run_id)
    kinds = [e.kind for e in run.events]
    assert EventKind.NODE_STARTED in kinds
    assert EventKind.NODE_FINISHED in kinds
    assert run.node_status["planner"].value == "done"


async def test_planner_followup_appends_gap_questions(deps, db) -> None:
    # Existing plan + a quality verdict with missing areas → append new questions.
    deps.llm = FakeLLMClient({"PlanResult": [make_plan(n=3)]})
    node = build_planner(deps)
    state = base_state(
        plan=[{"id": "q0", "question": "old?", "rationale": "r"}],
        quality={
            "coverage_score": 0.5,
            "confidence_score": 0.5,
            "missing_areas": ["pricing", "hiring"],
            "needs_more_research": True,
        },
    )

    update, _ = await invoke_node(node, state, db)

    plan = update["plan"]
    assert len(plan) == 4  # 1 existing + 3 new
    assert plan[0]["id"] == "q0"  # original preserved
    assert plan[1]["id"] == "q1"  # new ids continue from the end
    # The follow-up prompt must mention the missing areas.
    assert "pricing" in deps.llm.calls[-1]["user"]
