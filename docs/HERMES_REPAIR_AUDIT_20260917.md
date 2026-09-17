# UI Binder - Hermes Repair Audit 20260917

## Source
- **repo**: `https://github.com/klssxx/ui-binder`
- **branch (start)**: `work/v0.3-ux-premium` (`e8b03b1`)
- **branch (end)**: `repair/uibinder-hermes-long-20260917` (`09215f9`)
- **OS**: Windows 11 (MSYS/Git Bash)
- **Python**: 3.12.10
- **Node**: v22.23.1

## Baseline
| check | result | evidence |
|---|---|---|
| pytest | 80 passed, rc=0 | `.venv/Scripts/python.exe -m pytest tests -q` |
| vitest | 6 passed, rc=0 | `npm test` |
| build | exit 0, 49 modules | `npm run build` |
| typecheck | exit 0 | `npm run typecheck` |
| compileall | no errors | `python -m compileall backend adapters scripts tests` |
| working tree | clean | `git status` before repair |
| remote | `klssxx/ui-binder` | `git remote -v` |

## Findings

| ID | severity | file | problem | status |
|---|---|---|---|---|
| F001 | P0 | backend/security/paths.py | `is_safe_export_target` allowed exports to `C:\Windows` and drive roots | FIXED |
| F002 | P1 | backend/analyzer/project_scanner.py | `break` on ignored dir aborts entire scan | FIXED |
| F003 | P2 | backend/api/verification.py:107 | `except Exception: pass` silently swallows heuristic errors | FIXED |
| F004 | INFO | README.md | Test count stale (74 vs actual 80, then 106) | FIXED |
| F005 | INFO | STATE.json | Cited obsolete commit bee6089 | FIXED |

## Changes by module

### backend/security/paths.py
- Added `_FORBIDDEN_PROJECT_PARENTS` check in `is_safe_export_target` (lines 50-57)
- Added drive-root rejection (parent == target)

### backend/analyzer/project_scanner.py
- Line 33: `break` → `continue` in `scan_project` is_dir branch

### backend/api/verification.py
- Lines 107-108: `except Exception: pass` → logs WARNING with exception context

### README.md
- Line 65: backend test count 74 → 106

### STATE.json
- Updated phase to REPAIR_HERMES_20260917, branch, commit, test counts

## Tests
| command | exit | passed | failed | skipped |
|---|---|---|---|---|
| `pytest tests -q` | 0 | 106 | 0 | 0 |
| `npm test` | 0 | 6 | 0 | 0 |

New test files:
- `tests/test_security.py` (12 tests): export path traversal, import path traversal, secret redaction
- `tests/test_project_scanner.py` (3 tests): ignored dir walk, requirements detection, dot-dir filtering

## Runtime verification
- Backend smoke: `/api/health` returns `{"status": "ok"}`
- Workspace CRUD: create → list → get
- Project import: `samples/sample_app` → 11 files, frameworks [fastapi, react, vite]
- Project analyze: 26 capabilities, 13 edges
- Export dry-run: returns plan with mode `export-to-new-directory`
- Export apply: creates package.json, vite.config.ts, tsconfig.json, index.html, src/main.tsx, src/App.tsx, src/api.ts, src/bindings.json
- Matcher scoring: deterministic (same comp + cap = same score)

## Workflows verified
1. **Backend startup** - VERIFIED
2. **Health endpoint** - VERIFIED
3. **Workspace create/list** - VERIFIED
4. **Project import (read-only)** - VERIFIED
5. **Project analyze** - VERIFIED
6. **Capabilities detection** - VERIFIED
7. **Suggest bindings** - VERIFIED
8. **Export plan (dry-run)** - VERIFIED
9. **Export apply (creates valid Vite project)** - VERIFIED
10. **Frontend build** - VERIFIED
11. **Typecheck** - VERIFIED

## Visual verification
- None performed headlessly; front-end behavior not modified.

## Remaining limitations
- **tauri-msvc**: Tauri installer blocked (no MSVC C++ Build Tools on host)
- **OCR**: rapidonnxruntime model not bundled in venv (works in packaged exe only)
- **Connected preview**: live project calls require running backend at origin
- **No LLM integration**: heuristic vision only; OCR optional

## Security findings
- **F001 FIXED**: export no longer accepts system dirs (prevents data corruption / path traversal)
- **Secret redaction**: `_redact()` covers `api_key`, `token`, `password`, `authorization`, Bearer tokens — VERIFIED by tests
- **No secrets in git**: `.env` in `.gitignore`, `data/` excluded
- **Path traversal**: `ensure_inside` for import reads; export validated separately
- **SQLite**: WAL mode, short-lived connections, connection timeout=30s
- **Pruning**: startup retention caps prevent unbounded DB growth

## Documentation reconciled
- README.md test count corrected
- STATE.json updated to reflect repair branch and current commit

## Commits
| SHA | message |
|---|---|
| `5cfd03d` | fix: harden export safety against system dirs and drive roots |
| `7c8f43d` | fix: project scanner aborted entire walk on ignored dirs |
| `09215f9` | fix: log instead of silently swallowing region detection errors |

## Remote branch
`repair/uibinder-hermes-long-20260917` (push pending at time of writing)

## Exact next recommended step
Push to GitHub and open PR if promotion to main is desired.
