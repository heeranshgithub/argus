#!/usr/bin/env python
"""Run the research workflow against REAL providers (OpenRouter + Tavily).

Not a test — a manual smoke tool for verifying prompts/quality before Part 4.
Creates a session, runs the graph to completion while tailing live events, then
prints the generated report.

Usage (from ``backend/``, with a populated ``.env``)::

    uv run python scripts/run_workflow.py \
        --company "Stripe" \
        --website "https://stripe.com" \
        --objective "Explore a payments partnership"

Requires ``OPENROUTER_API_KEY`` (and ideally ``TAVILY_API_KEY``) in the env.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from app.config import get_settings
from app.db.mongo import ensure_indexes, mongo_manager
from app.models.session import SessionCreate
from app.repositories import report_repo, session_repo, workflow_repo
from app.workflow.deps import WorkflowDeps
from app.workflow.events import event_bus
from app.workflow.runner import WorkflowRunner

_TERMINAL = {"run_completed", "run_failed"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Argus research workflow.")
    parser.add_argument("--company", default="Stripe")
    parser.add_argument("--website", default="https://stripe.com")
    parser.add_argument("--objective", default="Explore a payments partnership")
    return parser.parse_args()


async def _tail_events(session_id: str) -> None:
    """Print live workflow events for a session until it terminates."""
    queue = event_bus.subscribe(session_id)
    try:
        while True:
            event = await queue.get()
            node = event["node"]
            kind = event["kind"]
            extra = ""
            if kind == "node_finished":
                extra = f"  {json.dumps(event['payload'])[:120]}"
            print(f"  [{event['seq']:>2}] {kind:<14} {node}{extra}")
            if kind in _TERMINAL:
                return
    finally:
        event_bus.unsubscribe(session_id, queue)


def _print_report(report) -> None:
    print("\n" + "=" * 70)
    print("REPORT")
    print("=" * 70)
    print(f"\n## Company Overview\n{report.company_overview}")
    print("\n## Products & Services\n- " + "\n- ".join(report.products_and_services))
    print("\n## Target Customers\n- " + "\n- ".join(report.target_customers))
    print("\n## Business Signals")
    for sig in report.business_signals:
        print(f"- [{sig.category}] {sig.summary} (conf {sig.confidence:.2f})")
    print("\n## Risks & Challenges\n- " + "\n- ".join(report.risks_and_challenges))
    print("\n## Suggested Discovery Questions")
    for dq in report.suggested_discovery_questions:
        print(f"- {dq.question}\n    ↳ {dq.rationale}")
    print(f"\n## Suggested Outreach Strategy\n{report.suggested_outreach_strategy}")
    print("\n## Unknowns\n- " + "\n- ".join(report.unknowns))
    print(f"\n## Sources ({len(report.sources)})")
    for src in report.sources:
        print(f"- {src.title} — {src.url}  (used in: {', '.join(src.used_in)})")


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    mongo_manager.connect(settings)
    if not await mongo_manager.ping():
        raise SystemExit("MongoDB is unreachable; start it before running this script.")
    db = mongo_manager.db
    await ensure_indexes(db)

    deps = WorkflowDeps.from_settings(settings)
    session = await session_repo.create(
        db,
        SessionCreate(
            company_name=args.company, website=args.website, objective=args.objective
        ),
    )
    print(f"Session {session.id} created for {args.company!r}")
    print(f"Search provider: {type(deps.search).__name__}\n")

    runner = WorkflowRunner(db, deps)
    run_id = await runner.start(session.id)

    tail = asyncio.create_task(_tail_events(session.id))
    print("Running workflow (live events):")
    await runner.execute(run_id, session.id)
    await tail

    run = await workflow_repo.get_run(db, run_id)
    print(f"\nRun {run_id} → {run.status.value}")
    if run.error:
        print(f"ERROR: {run.error.code}: {run.error.message}")
        await mongo_manager.disconnect()
        return

    report = await report_repo.get_by_session(db, session.id)
    if report is not None:
        _print_report(report)
    await mongo_manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
