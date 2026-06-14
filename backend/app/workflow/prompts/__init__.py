"""Focused, per-node prompts.

Each node owns a small, intent-documented prompt rather than sharing one
monolithic system prompt. Prompts return the *system* string; the per-call
*user* string (with the concrete session/source material) is assembled in the
node so the static instruction and the dynamic data stay cleanly separated.
"""
