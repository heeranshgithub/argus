"""Quality-check prompt — gate report readiness; drive the conditional edge."""

QUALITY_CHECK_SYSTEM = """\
You are the quality gate of a sales-research workflow. Judge whether the gathered
material is strong enough to write a complete final report covering these nine
sections:
  1. company overview
  2. products & services
  3. target customers
  4. business signals
  5. risks & challenges
  6. suggested discovery questions
  7. suggested outreach strategy
  8. unknowns
  9. sources

Assess:
- coverage_score [0,1]: how well the nine sections can be supported right now.
- confidence_score [0,1]: how trustworthy/consistent the evidence is (penalize
  contradictions and thin, single-source claims).
- missing_areas: specific topics still under-covered (drives another research
  pass). Empty if coverage is good.
- needs_more_research: true ONLY if another search pass would materially improve
  the report. If coverage is already adequate, set it false even if minor gaps
  remain — do not loop forever.

Be decisive. Borderline-adequate material should pass (needs_more_research=false).
"""


def quality_check_user(
    objective: str,
    analysis_block: str,
    signals_block: str,
    source_count: int,
    iteration: int,
) -> str:
    """Build the quality gate's user message."""
    return (
        f"Objective: {objective}\n"
        f"Research iteration so far: {iteration}\n"
        f"Number of sources gathered: {source_count}\n\n"
        f"Current analysis:\n{analysis_block}\n\n"
        f"Extracted signals:\n{signals_block}\n\n"
        "Return your quality verdict now."
    )
