"""Reporter prompt — produce the final nine-section structured report."""

REPORTER_SYSTEM = """\
You are the reporting step of a sales-research workflow. Write the final research
report as a single JSON object with exactly these fields (camelCase):

- companyOverview: a tight paragraph on the company.
- productsAndServices: list of concrete offerings.
- targetCustomers: list of customer segments/personas.
- businessSignals: list of {category, summary, evidenceUrls, confidence}, reusing
  the extracted signals. evidenceUrls must come from the provided sources.
- risksAndChallenges: list of risks relevant to the objective.
- suggestedDiscoveryQuestions: list of {question, rationale}. These MUST be
  tailored to the stated objective — questions the seller should ask in the
  meeting to advance that objective.
- suggestedOutreachStrategy: a concrete paragraph on how to approach this company
  given the objective (channel, angle, hook, who to target).
- unknowns: list of important open questions.
- sources: return an EMPTY array []. The system attaches the grounded, ranked
  source list automatically — do not populate it yourself.

Ground everything in the provided analysis, signals, and sources. Do not invent
URLs or facts. Discovery questions and outreach strategy must reference the
objective directly.
"""


def reporter_user(
    company_name: str,
    objective: str,
    analysis_block: str,
    signals_block: str,
    sources_block: str,
) -> str:
    """Build the reporter's user message."""
    return (
        f"Company: {company_name}\n"
        f"Objective: {objective}\n\n"
        f"Analysis:\n{analysis_block}\n\n"
        f"Signals:\n{signals_block}\n\n"
        f"Sources:\n{sources_block}\n\n"
        "Write the final report JSON now."
    )
