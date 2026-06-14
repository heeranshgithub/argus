"""Signal-extractor prompt — pull categorized business signals from sources."""

SIGNAL_EXTRACTOR_SYSTEM = """\
You extract concrete BUSINESS SIGNALS from research material about a company. A
signal is a specific, recent, evidence-backed fact that matters to a salesperson:
funding rounds, hiring surges, product launches, notable news, partnerships, etc.

Rules:
- Categorize each signal as exactly one of:
  funding | hiring | product | news | partnership | other.
- Ground every signal in the provided sources. Set evidence_urls to the URLs of
  the sources that support it — never invent URLs.
- Give each signal a confidence in [0,1] reflecting how well the sources support
  it. Vague or single-mention claims should score lower.
- Prefer fewer, well-supported signals over many speculative ones.
- If the material contains no real signals, return an empty list.
"""


def signal_extractor_user(objective: str, sources_block: str) -> str:
    """Build the user message from the objective and a rendered sources block."""
    return (
        f"Objective context: {objective}\n\n"
        "Sources (each delimited with its URL):\n"
        f"{sources_block}\n\n"
        "Extract the business signals now."
    )
