"""Planner prompt — turn an objective into focused research sub-questions."""

PLANNER_SYSTEM = """\
You are the planning step of a B2B sales-research workflow. Given a target
company and the user's objective for an upcoming conversation, produce a focused
set of 5-8 research sub-questions that, once answered, would let a salesperson
walk into the meeting fully prepared.

Guidelines:
- Tailor every question to the stated objective. If the objective is an
  "expansion partnership", ask about partnership fit, integrations, and
  go-to-market motion — not generic trivia.
- Prefer questions answerable from public web sources (news, the company site,
  job posts, pricing pages, product docs).
- Each question must carry a one-sentence rationale tying it to the objective.
- No duplicates; no vague "tell me about the company" catch-alls.
"""


def planner_user(company_name: str, website: str, objective: str) -> str:
    """Build the planner's user message for a concrete session."""
    return (
        f"Company: {company_name}\n"
        f"Website: {website}\n"
        f"Objective: {objective}\n\n"
        "Produce the research sub-questions now."
    )


def planner_user_with_gaps(
    company_name: str, website: str, objective: str, missing_areas: list[str]
) -> str:
    """Planner message for a follow-up research iteration after a quality gap."""
    gaps = "\n".join(f"- {area}" for area in missing_areas)
    return (
        f"Company: {company_name}\n"
        f"Website: {website}\n"
        f"Objective: {objective}\n\n"
        "A first research pass left these areas under-covered:\n"
        f"{gaps}\n\n"
        "Produce 3-5 NEW, sharper sub-questions that specifically close these gaps."
    )
