"""Researcher node tests — gathering, fallback, incrementality, failure."""

from app.repositories import workflow_repo
from app.workflow.nodes.researcher import build_researcher
from app.workflow.tools.fetch import FetchError
from tests.workflow.conftest import FakeFetcher, FakeSearchClient, base_state, invoke_node


async def test_researcher_gathers_sources_and_crawls_site(deps, db) -> None:
    node = build_researcher(deps)
    plan = [{"id": "q0", "question": "What does Acme do?", "rationale": "r"}]

    update, run_id = await invoke_node(node, base_state(plan=plan), db)

    assert update["research_iteration"] == 1
    assert update["researched_question_ids"] == ["q0"]
    assert len(update["raw_sources"]) >= 1
    # Search ran for the question; the site crawl added homepage/about/etc.
    assert deps.search.calls == ["What does Acme do?"]

    run = await workflow_repo.get_run(db, run_id)
    assert run.node_status["researcher"].value == "done"


async def test_researcher_falls_back_to_snippet_on_fetch_error(settings) -> None:
    from mongomock_motor import AsyncMongoMockClient

    from app.workflow.deps import WorkflowDeps
    from app.workflow.tools.llm import FakeLLMClient

    db = AsyncMongoMockClient(tz_aware=True)["argus_test"]

    class BrokenFetcher(FakeFetcher):
        async def fetch(self, url: str):
            raise FetchError(url, "boom")

    deps = WorkflowDeps(
        llm=FakeLLMClient(),
        search=FakeSearchClient(),
        fetcher=BrokenFetcher(),
        settings=settings,
    )
    node = build_researcher(deps)
    plan = [{"id": "q0", "question": "q?", "rationale": "r"}]

    update, _ = await invoke_node(node, base_state(plan=plan), db)

    # Fetches all failed, but search snippets keep us afloat (errors recorded).
    assert update["raw_sources"]
    assert all(src["content"] for src in update["raw_sources"])
    assert update["errors"]
    assert any(e.get("error") for e in update["errors"])


async def test_researcher_only_researches_new_questions(deps, db) -> None:
    node = build_researcher(deps)
    plan = [
        {"id": "q0", "question": "old?", "rationale": "r"},
        {"id": "q1", "question": "new?", "rationale": "r"},
    ]
    state = base_state(
        plan=plan,
        research_iteration=1,
        researched_question_ids=["q0"],
        raw_sources=[
            {"url": "https://x", "title": "x", "snippet": "", "content": "c", "fetched_at": "t"}
        ],
    )

    update, _ = await invoke_node(node, state, db)

    assert deps.search.calls == ["new?"]  # q0 skipped
    assert update["researched_question_ids"] == ["q1"]
    assert update["research_iteration"] == 2


async def test_researcher_raises_when_nothing_gathered(settings, db) -> None:
    from app.workflow.deps import WorkflowDeps
    from app.workflow.tools.llm import FakeLLMClient

    class EmptySearch(FakeSearchClient):
        async def search(self, query: str, k: int = 5):
            return []

    class EmptyFetcher(FakeFetcher):
        async def fetch(self, url: str):
            raise FetchError(url, "404")

    deps = WorkflowDeps(
        llm=FakeLLMClient(),
        search=EmptySearch(),
        fetcher=EmptyFetcher(),
        settings=settings,
    )
    node = build_researcher(deps)
    plan = [{"id": "q0", "question": "q?", "rationale": "r"}]

    # No search results, all crawl fetches fail, no prior sources → node fails.
    try:
        await invoke_node(node, base_state(plan=plan), db)
        raised = False
    except RuntimeError:
        raised = True
    assert raised
