"""Lightweight retrieval for follow-up chat (PLAN_PART_5 §1.3).

BM25 over the run's raw sources keeps dependencies and latency low while giving
good-enough ranking for the ≤50-source scale we operate at. Swapping in an
embedding retriever later is a drop-in behind :func:`pack.select_sources`.
"""
