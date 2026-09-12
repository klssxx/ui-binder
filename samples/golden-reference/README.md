# Golden Reference

Reproducible regression sample for UI Binder.

- `reference.png` — synthetic screenshot, generated deterministically by
  `scripts/make_golden.py` (no manual screenshots involved).
- `expected_ui_schema.json` — structural invariants the vision pipeline must satisfy.
- `expected_capabilities.json` — what the analyzers must find in `samples/sample_app`.
- `expected_bindings.json` — Smart Binder expectations for the Generate button.

Regenerate the image: `python scripts/make_golden.py`
Run the gate: `pytest tests/test_vision.py tests/test_smoke_e2e.py -q`
