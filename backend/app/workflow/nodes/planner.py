"""``planner`` node — objective → focused research sub-questions.

On a fresh run it generates the initial plan. When ``quality_check`` loops back
(``research_iteration`` already advanced and ``quality.missing_areas`` set) it
generates sharper gap-closing questions and *appends* them to the existing plan.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.logging_config import get_logger
from app.workflow.deps import WorkflowDeps
from app.workflow.events import emit_node
from app.workflow.prompts.planner import (
    PLANNER_SYSTEM,
    planner_user,
    planner_user_with_gaps,
)
from app.workflow.schemas import PlanResult
from app.workflow.state import GraphState, SubQuestion

log = get_logger("workflow.node.planner")

NodeFn = Callable[[GraphState], Awaitable[dict[str, Any]]]


def build_planner(deps: WorkflowDeps) -> NodeFn:
    """Build the planner node bound to ``deps``."""
    model = deps.settings.model_for_node("planner")

    async def planner(state: GraphState) -> dict[str, Any]:
        async with emit_node("planner") as ev:
            existing = state.get("plan") or []
            quality = state.get("quality")
            missing = quality["missing_areas"] if quality else []
            is_followup = bool(existing) and bool(missing)

            if is_followup:
                user = planner_user_with_gaps(
                    state["company_name"],
                    state["website"],
                    state["objective"],
                    missing,
                )
            else:
                user = planner_user(
                    state["company_name"], state["website"], state["objective"]
                )

            result = await deps.llm.complete(
                PLANNER_SYSTEM, user, response_model=PlanResult, model=model
            )

            start_idx = len(existing)
            new_questions: list[SubQuestion] = [
                SubQuestion(
                    id=f"q{start_idx + i}",
                    question=q.question,
                    rationale=q.rationale,
                )
                for i, q in enumerate(result.questions)
            ]
            plan = [*existing, *new_questions]

            ev.set_preview({"new_questions": len(new_questions), "total": len(plan)})
            log.info(
                "planner_done",
                followup=is_followup,
                new_questions=len(new_questions),
                total=len(plan),
            )
            return {"plan": plan}

    return planner
