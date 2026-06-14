"""LLM abstraction: ``LLMClient`` protocol + OpenRouter impl + deterministic fake.

OpenRouter is the single gateway — one OpenAI-compatible endpoint proxying to
hundreds of models. The model is just a config string, so nodes can pin cheap
models for cheap work and stronger ones for synthesis (see PLAN_PART_3 §11).

Structured output is handled defensively: not every model behind OpenRouter
supports native JSON-schema response formats, so we always include the schema in
the prompt, request JSON mode, parse, Pydantic-validate, and do exactly one
repair retry on validation failure. Transport errors (429/5xx/timeout) get three
attempts with exponential backoff.
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, overload, runtime_checkable

from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.config import Settings

log = get_logger("workflow.llm")

M = TypeVar("M", bound=BaseModel)

# Strip ```json … ``` fences some models wrap JSON in despite instructions.
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class LLMError(Exception):
    """Raised when the LLM cannot produce valid output after retries."""


@runtime_checkable
class LLMClient(Protocol):
    """Completes a system+user prompt, optionally into a Pydantic model."""

    @overload
    async def complete(
        self,
        system: str,
        user: str,
        *,
        response_model: type[M],
        model: str | None = ...,
        temperature: float = ...,
        max_tokens: int = ...,
        fallback_models: list[str] | None = ...,
    ) -> M: ...

    @overload
    async def complete(
        self,
        system: str,
        user: str,
        *,
        response_model: None = ...,
        model: str | None = ...,
        temperature: float = ...,
        max_tokens: int = ...,
        fallback_models: list[str] | None = ...,
    ) -> str: ...

    async def complete(
        self,
        system: str,
        user: str,
        *,
        response_model: type[BaseModel] | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        fallback_models: list[str] | None = None,
    ) -> str | BaseModel: ...


# Model-slug prefixes whose providers support native strict JSON-schema output.
# For these we force the exact shape server-side; others get prompt-based JSON.
_STRICT_CAPABLE_PREFIXES = ("openai/", "google/gemini")


def _is_strict_capable(model: str) -> bool:
    return model.startswith(_STRICT_CAPABLE_PREFIXES)


def _strip_fences(text: str) -> str:
    """Remove surrounding markdown code fences from a JSON blob."""
    return _FENCE_RE.sub("", text).strip()


def _to_strict_schema(response_model: type[BaseModel]) -> dict[str, Any]:
    """Render a Pydantic model as an OpenAI strict-mode JSON Schema.

    Strict mode requires every object to set ``additionalProperties: false`` and
    list *all* its properties as ``required``, and it rejects ``default``. We
    transform Pydantic's schema (recursively, including ``$defs``) to comply.
    """
    schema = response_model.model_json_schema()

    def _harden(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            node.pop("default", None)
            for value in node.values():
                _harden(value)
        elif isinstance(node, list):
            for item in node:
                _harden(item)

    _harden(schema)
    return schema


def _schema_instruction(response_model: type[BaseModel]) -> str:
    """Build the 'respond only with JSON matching this schema' instruction."""
    schema = json.dumps(response_model.model_json_schema(), indent=0)
    return (
        "Respond ONLY with a single JSON object matching this JSON Schema. "
        "Do not include any prose, explanation, or markdown code fences.\n"
        f"Schema:\n{schema}"
    )


class OpenRouterClient:
    """The single real LLM client, talking to OpenRouter via the OpenAI SDK."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openrouter_api_key:
            raise LLMError(
                "OPENROUTER_API_KEY is not set; cannot construct OpenRouterClient. "
                "Set it in the environment or use FakeLLMClient in tests."
            )
        from openai import AsyncOpenAI

        headers: dict[str, str] = {"X-Title": settings.openrouter_app_title}
        if settings.openrouter_app_url:
            headers["HTTP-Referer"] = settings.openrouter_app_url

        self._client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers=headers,
        )
        self._default_model = settings.llm_model_default
        self._default_fallbacks = settings.llm_fallback_models

    @overload
    async def complete(
        self, system: str, user: str, *, response_model: type[M],
        model: str | None = ..., temperature: float = ..., max_tokens: int = ...,
        fallback_models: list[str] | None = ...,
    ) -> M: ...

    @overload
    async def complete(
        self, system: str, user: str, *, response_model: None = ...,
        model: str | None = ..., temperature: float = ..., max_tokens: int = ...,
        fallback_models: list[str] | None = ...,
    ) -> str: ...

    async def complete(
        self,
        system: str,
        user: str,
        *,
        response_model: type[BaseModel] | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        fallback_models: list[str] | None = None,
    ) -> str | BaseModel:
        model = model or self._default_model
        fallbacks = fallback_models if fallback_models is not None else self._default_fallbacks

        if response_model is None:
            return await self._call(
                system, user, model, temperature, max_tokens, fallbacks, response_format=None
            )

        # Capable models get native strict JSON-schema (exact shape enforced
        # server-side); the rest get JSON mode + the schema in the prompt. Both
        # paths parse + Pydantic-validate + do one repair retry on failure.
        if _is_strict_capable(model):
            response_format: dict[str, Any] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": _to_strict_schema(response_model),
                    "strict": True,
                },
            }
            sys = system
        else:
            response_format = {"type": "json_object"}
            sys = f"{system}\n\n{_schema_instruction(response_model)}"

        raw = await self._call(
            sys, user, model, temperature, max_tokens, fallbacks, response_format=response_format
        )
        try:
            return self._parse(raw, response_model)
        except (json.JSONDecodeError, ValidationError) as first_err:
            log.warning("llm_schema_retry", model=model, error=str(first_err)[:300])
            repair = (
                f"{user}\n\nYour previous response failed validation: {first_err}. "
                "Return ONLY corrected JSON that is an instance of the schema."
            )
            raw = await self._call(
                sys, repair, model, temperature, max_tokens, fallbacks,
                response_format=response_format,
            )
            try:
                return self._parse(raw, response_model)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise LLMError(
                    f"{response_model.__name__} validation failed after repair: {exc}"
                ) from exc

    @staticmethod
    def _parse(raw: str, response_model: type[BaseModel]) -> BaseModel:
        data = json.loads(_strip_fences(raw))
        return response_model.model_validate(data)

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _call(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float,
        max_tokens: int,
        fallbacks: list[str],
        *,
        response_format: dict[str, Any] | None,
    ) -> str:
        """One chat completion with retry on transient transport errors."""
        # Only retry transient transport errors; re-raise others immediately.
        from openai import (
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
        )

        extra_body: dict[str, Any] = {"usage": {"include": True}}
        if fallbacks:
            extra_body["models"] = fallbacks

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_body": extra_body,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        started = time.monotonic()
        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            InternalServerError,
        ) as exc:
            log.warning("llm_transient_error", model=model, error=type(exc).__name__)
            raise
        latency_ms = int((time.monotonic() - started) * 1000)

        usage = getattr(resp, "usage", None)
        log.info(
            "llm_call",
            model=getattr(resp, "model", model),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            cost_usd=getattr(usage, "cost", None),
            latency_ms=latency_ms,
            structured=response_format is not None,
        )
        content = resp.choices[0].message.content if resp.choices else None
        if not content:
            raise LLMError(f"Empty completion from model {model!r}.")
        return content


class FakeLLMClient:
    """Deterministic, network-free LLM for tests.

    Scripted by the Pydantic ``response_model`` name (or ``"text"`` for plain
    completions). Each call pops the next response for that key; when a queue is
    exhausted the last response repeats (so a node that retries doesn't blow up a
    test). A ``handler`` callable can override scripting entirely for fine control.
    """

    def __init__(
        self,
        by_model: dict[str, list[Any]] | None = None,
        *,
        handler: Any | None = None,
        repeat_last: bool = True,
    ) -> None:
        self._by_model: dict[str, list[Any]] = {
            k: list(v) for k, v in (by_model or {}).items()
        }
        self._handler = handler
        self._repeat_last = repeat_last
        self.calls: list[dict[str, Any]] = []

    @overload
    async def complete(
        self, system: str, user: str, *, response_model: type[M],
        model: str | None = ..., temperature: float = ..., max_tokens: int = ...,
        fallback_models: list[str] | None = ...,
    ) -> M: ...

    @overload
    async def complete(
        self, system: str, user: str, *, response_model: None = ...,
        model: str | None = ..., temperature: float = ..., max_tokens: int = ...,
        fallback_models: list[str] | None = ...,
    ) -> str: ...

    async def complete(
        self,
        system: str,
        user: str,
        *,
        response_model: type[BaseModel] | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        fallback_models: list[str] | None = None,
    ) -> str | BaseModel:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "model": model,
                "response_model": response_model.__name__ if response_model else None,
            }
        )
        if self._handler is not None:
            return self._handler(system, user, response_model)

        key = response_model.__name__ if response_model else "text"
        queue = self._by_model.get(key)
        if not queue:
            raise LLMError(f"FakeLLMClient has no scripted response for {key!r}.")
        value = queue.pop(0) if len(queue) > 1 or not self._repeat_last else queue[0]

        if response_model is not None and isinstance(value, dict):
            return response_model.model_validate(value)
        return value
