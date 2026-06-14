"""Report models — the camelCase wire shape for a generated research report.

Matches the assignment's nine required sections exactly (see PLAN_PART_3 §5).
All inherit :class:`ApiModel`, so the JSON wire is camelCase while the Python
attributes — and the Mongo document — stay snake_case. The ``_id`` → ``id``
conversion happens at the repository edge (see ``app.repositories.report_repo``)
so ``ObjectId`` never reaches Pydantic.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.base import ApiModel


class BusinessSignalOut(ApiModel):
    """A single detected business signal (funding, hiring, product, …)."""

    category: str
    summary: str
    evidence_urls: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class DiscoveryQuestion(ApiModel):
    """A suggested discovery question for the upcoming conversation."""

    question: str
    rationale: str


class ReportSource(ApiModel):
    """A cited source, with the report sections that referenced it."""

    url: str
    title: str
    used_in: list[str] = Field(default_factory=list)  # which sections cited it


class ReportOut(ApiModel):
    """A full research report as returned on the wire.

    The nine required sections are: company overview, products & services,
    target customers, business signals, risks & challenges, suggested discovery
    questions, suggested outreach strategy, unknowns, and sources.
    """

    id: str
    session_id: str
    company_overview: str
    products_and_services: list[str] = Field(default_factory=list)
    target_customers: list[str] = Field(default_factory=list)
    business_signals: list[BusinessSignalOut] = Field(default_factory=list)
    risks_and_challenges: list[str] = Field(default_factory=list)
    suggested_discovery_questions: list[DiscoveryQuestion] = Field(default_factory=list)
    suggested_outreach_strategy: str
    unknowns: list[str] = Field(default_factory=list)
    sources: list[ReportSource] = Field(default_factory=list)
    created_at: datetime


class ReportDraft(ApiModel):
    """The reporter node's LLM output — a report without persistence metadata.

    The ``reporter`` node produces this; ``report_repo`` stamps ``id``,
    ``session_id`` and ``created_at`` when it persists the document. Keeping the
    LLM-facing schema free of those server-owned fields means the model is never
    asked to invent an id or timestamp.
    """

    company_overview: str
    products_and_services: list[str] = Field(default_factory=list)
    target_customers: list[str] = Field(default_factory=list)
    business_signals: list[BusinessSignalOut] = Field(default_factory=list)
    risks_and_challenges: list[str] = Field(default_factory=list)
    suggested_discovery_questions: list[DiscoveryQuestion] = Field(default_factory=list)
    suggested_outreach_strategy: str
    unknowns: list[str] = Field(default_factory=list)
    sources: list[ReportSource] = Field(default_factory=list)
