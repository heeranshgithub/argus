# Architecture

> **Status:** stub — full content lands in Part 5.

## System Overview

```
┌──────────────┐      camelCase JSON      ┌──────────────┐      ┌──────────────┐
│   Frontend   │  ───────────────────────▶│   Backend    │─────▶│  LangGraph   │
│  Next.js +   │   (RTK Query / fetch)     │  FastAPI +   │      │  Workflow    │
│  RTK Query   │◀───────────────────────── │  Pydantic    │◀─────│  (nodes)     │
└──────────────┘                           └──────┬───────┘      └──────────────┘
                                                  │
                                                  ▼
                                           ┌──────────────┐
                                           │   MongoDB    │
                                           │  (Motor)     │
                                           └──────────────┘
```

## Outline (to be filled in)

- Component responsibilities (frontend, API, workflow, persistence)
- The camelCase ↔ snake_case naming bridge
- LangGraph node graph and shared state
- Data model and collections
- Request lifecycle and error contract
- Real-time progress (SSE) design
- Recoverability via the LangGraph checkpointer
