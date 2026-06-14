# Argus Backend

FastAPI + Motor (MongoDB) + LangGraph backend for the Argus AI Research Copilot.

See the root [`README.md`](../README.md) for the full quickstart. Quick local run:

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Then `GET http://localhost:8000/api/health`.
