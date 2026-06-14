"""OpenRouterClient tests with a mocked OpenAI SDK (no network)."""

import openai
import pytest

from app.config import Settings
from app.workflow.schemas import PlanResult
from app.workflow.tools.llm import LLMError, OpenRouterClient


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)


class _Usage:
    prompt_tokens = 10
    completion_tokens = 5
    cost = 0.0001


class _Resp:
    model = "openai/gpt-4o-mini"
    usage = _Usage()

    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._contents[min(len(self.calls) - 1, len(self._contents) - 1)]
        return _Resp(content)


class _Chat:
    def __init__(self, contents: list[str]) -> None:
        self.completions = _Completions(contents)


class _FakeOpenAI:
    last: "_FakeOpenAI | None" = None

    def __init__(self, contents: list[str], **kwargs) -> None:
        self.chat = _Chat(contents)
        self.init_kwargs = kwargs


def _patch(monkeypatch, contents: list[str]) -> None:
    def factory(**kwargs):
        client = _FakeOpenAI(contents, **kwargs)
        _FakeOpenAI.last = client
        return client

    monkeypatch.setattr(openai, "AsyncOpenAI", factory)


def _settings() -> Settings:
    return Settings(env="test", openrouter_api_key="sk-test", openrouter_app_url="https://argus")


async def test_complete_plain_text(monkeypatch) -> None:
    _patch(monkeypatch, ["hello there"])
    client = OpenRouterClient(_settings())
    out = await client.complete("sys", "user")
    assert out == "hello there"
    # JSON mode is off for plain text; headers include referer + title.
    assert _FakeOpenAI.last.chat.completions.calls[0].get("response_format") is None
    assert _FakeOpenAI.last.init_kwargs["default_headers"]["X-Title"]


async def test_structured_output_uses_native_schema_for_openai(monkeypatch) -> None:
    _patch(monkeypatch, ['{"questions":[{"question":"q","rationale":"r"}]}'])
    client = OpenRouterClient(_settings())  # default model is openai/gpt-4o-mini
    out = await client.complete("sys", "user", response_model=PlanResult)
    assert isinstance(out, PlanResult)
    assert out.questions[0].question == "q"

    rf = _FakeOpenAI.last.chat.completions.calls[0]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    # Strict schema hardening: every object requires all props, no extras.
    schema = rf["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"questions"}


async def test_structured_output_prompt_json_for_non_strict_model(monkeypatch) -> None:
    _patch(monkeypatch, ['{"questions":[{"question":"q","rationale":"r"}]}'])
    client = OpenRouterClient(_settings())
    out = await client.complete(
        "sys", "user", response_model=PlanResult, model="anthropic/claude-sonnet-4.6"
    )
    assert isinstance(out, PlanResult)
    call = _FakeOpenAI.last.chat.completions.calls[0]
    # Anthropic path: JSON mode + schema embedded in the system prompt.
    assert call["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in call["messages"][0]["content"]


async def test_structured_output_repairs_once(monkeypatch) -> None:
    # First response is invalid JSON; the repair attempt succeeds.
    _patch(monkeypatch, ["not json", '{"questions":[{"question":"q","rationale":"r"}]}'])
    client = OpenRouterClient(_settings())
    out = await client.complete("sys", "user", response_model=PlanResult)
    assert isinstance(out, PlanResult)
    assert len(_FakeOpenAI.last.chat.completions.calls) == 2


async def test_structured_output_raises_after_failed_repair(monkeypatch) -> None:
    _patch(monkeypatch, ["nope", "still nope"])
    client = OpenRouterClient(_settings())
    with pytest.raises(LLMError):
        await client.complete("sys", "user", response_model=PlanResult)


async def test_empty_completion_raises(monkeypatch) -> None:
    _patch(monkeypatch, [""])
    client = OpenRouterClient(_settings())
    with pytest.raises(LLMError):
        await client.complete("sys", "user")


async def test_strips_markdown_fences(monkeypatch) -> None:
    fenced = '```json\n{"questions":[{"question":"q","rationale":"r"}]}\n```'
    _patch(monkeypatch, [fenced])
    client = OpenRouterClient(_settings())
    out = await client.complete("sys", "user", response_model=PlanResult)
    assert isinstance(out, PlanResult)
