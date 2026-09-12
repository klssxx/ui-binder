# Sample App (E2E target)

Minimal but real application used by UI Binder tests and smoke flows.

- `backend/` — FastAPI: POST /api/generate (input → button → API → result),
  plus unrouted services (`export_report`, `restore_session`, `load_history`,
  `evaluate_idea`) that the orphan detector must classify as UNBOUND, never delete.
- `frontend/` — React + Vite: `IdeaInput`, `GenerateButton`, `ResultPanel`,
  `handleGenerate` calling `fetch('/api/generate')`.

Run backend: `python -m uvicorn app.api... ` — or simply:
`cd backend && python -m uvicorn app:app --port 8901` (add fastapi to your env).

Expected analyzer results are asserted in `tests/test_smoke_e2e.py` and
`samples/golden-reference/expected_capabilities.json`.
