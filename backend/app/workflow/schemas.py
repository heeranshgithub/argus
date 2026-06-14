"""Pydantic schemas for structured LLM input/output inside the graph.

These are plain ``BaseModel`` (snake_case, no camelCase aliasing) because they
are fed to the LLM as a JSON Schema and parsed straight back — keeping field
names identical on both sides avoids translation bugs. Nodes convert these into
the ``GraphState`` TypedDicts. The reporter is the exception: it emits the
wire-facing :class:`app.models.report.ReportDraft` directly.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlannedQuestion(BaseModel):
    """One planned research sub-question (the planner assigns ids)."""

    question: str
    rationale: str


class PlanResult(BaseModel):
    """The planner's output: a focused set of sub-questions."""

    questions: list[PlannedQuestion] = Field(min_length=1)


class ExtractedSignal(BaseModel):
    """A single business signal pulled from the gathered sources."""

    category: str = Field(
        description="One of: funding, hiring, product, news, partnership, other"
    )
    summary: str
    evidence_urls: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class SignalsResult(BaseModel):
    """The signal extractor's output."""

    signals: list[ExtractedSignal] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """The analyst's structured synthesis (maps to ``AnalysisBlock``)."""

    overview: str
    products_services: list[str] = Field(default_factory=list)
    target_customers: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class QualityResult(BaseModel):
    """The quality gate's verdict (maps to ``QualityVerdict``)."""

    coverage_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    missing_areas: list[str] = Field(default_factory=list)
    needs_more_research: bool
