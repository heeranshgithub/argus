"""Analyst prompt — synthesize sources + signals into a structured analysis."""

ANALYST_SYSTEM = """\
You are the analysis step of a sales-research workflow. Synthesize the gathered
sources and extracted signals into a structured assessment of the company,
viewed through the lens of the user's objective.

Produce:
- overview: 2-4 sentences on what the company does and its current trajectory.
- products_services: concrete products/services/offerings (short phrases).
- target_customers: who the company sells to (segments, personas, industries).
- risks: risks/challenges relevant to the objective (competitive, financial,
  operational, regulatory).
- unknowns: important questions the available material did NOT answer.

Be specific and grounded — do not pad. If something is genuinely unclear, put it
in unknowns rather than guessing.
"""


def analyst_user(
    company_name: str, objective: str, signals_block: str, sources_block: str
) -> str:
    """Build the analyst's user message."""
    return (
        f"Company: {company_name}\n"
        f"Objective: {objective}\n\n"
        f"Extracted signals:\n{signals_block}\n\n"
        f"Sources:\n{sources_block}\n\n"
        "Produce the structured analysis now."
    )
