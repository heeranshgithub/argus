"""Graph nodes.

Each module exposes a ``build_<name>(deps)`` factory returning an
``async def node(state) -> dict`` that returns a *partial* ``GraphState`` update.
Factories close over :class:`app.workflow.deps.WorkflowDeps` so nodes depend only
on protocols and stay unit-testable in isolation.
"""
