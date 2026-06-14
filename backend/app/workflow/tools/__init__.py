"""External-world tool abstractions: LLM, web search, page fetch, text cleanup.

Each capability is a ``Protocol`` with a real implementation (network) and a
deterministic fake (tests). Nodes depend only on the protocols, so the whole
graph runs offline under pytest and against live providers from a script.
"""
