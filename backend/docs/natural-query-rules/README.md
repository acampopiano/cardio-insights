# Natural Query Language Rules

These files define language interpretation rules for the natural query parser.

- `temporal.json`: month aliases and granularity tokens.
- `intent.json`: ranking/top intent markers.
- `metrics.json`: metric keyword mappings and auto-KPI triggers.

## How loading works

1. The service first tries this split-directory layout (`docs/natural-query-rules/`).
2. If files are missing or invalid, it falls back to the legacy single file:
   - `docs/natural-query-language-rules.json`
3. If both fail, built-in defaults are used.

## Editing guidance

- Keep tokens normalized without accents (service normalizes input).
- Add short stems when possible (`cirug`, `hemodinam`) to cover variants.
- After edits, run backend tests:

```powershell
cd backend
python -m pytest -q
```
