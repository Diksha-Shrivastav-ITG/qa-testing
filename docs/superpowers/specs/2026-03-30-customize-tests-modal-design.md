# Customize Tests Modal — Design Spec

**Date:** 2026-03-30
**Branch:** diksha-qa

---

## Goal

Replace the "Test Cases" tab on the project detail page with a smarter Start QA modal that lets users choose either "Full QA" (run everything) or "Customize" (pick which of the 5 test phases to run). Backend skips unchecked phases.

---

## What Changes

### Removed
- `ProjectDetailPage.tsx`: The entire "Test Cases" tab — nav item, `TEST_CASES` array, `enabledTests` state, `toggleTest` function, `testCategories` variable, and the tab content block (~60 lines).

### Modified: `RunQAModal.tsx`
- Add a **Full QA | Customize** tab bar at the top of the modal body.
- **Full QA tab** (default): Existing modal content unchanged (page selector + testing mode radios). Button: "🚀 Start QA Run". Passes no `test_types` — backend runs all phases.
- **Customize tab**: Same page selector + same testing mode radios + **5 test checkboxes** (all checked by default):
  1. 🔍 QA Test — Visual AI analysis & design comparison
  2. ⚡ Functionality Test — Cart, checkout, search, mobile menu
  3. ♿ ADA Test — WCAG 2.1 accessibility compliance
  4. 🔎 SEO Test — GTM, GA4, GSC, Bing, meta tags
  5. 📊 Performance Test — Load time, TTFB, resource size
- Button: "⚙️ Run Selected Tests". **Disabled** when 0 checkboxes are checked.
- Passes `test_types: string[]` to API (only checked items).

### Modified: `frontend/src/api/runs.ts`
- `startRun(projectId, pages, testMode, testTypes?)` — optional `test_types` appended to query string when provided.

### Modified: `backend/app/routers/runs.py`
- Accept `test_types: list[str] | None = Query(None)`.
- Pass to `run_qa_job.delay(...)`.

### Modified: `backend/app/workers/qa_tasks.py`
- `run_qa_job` and `_run_qa_job_async` accept `test_types: list[str] | None = None`.
- Phase skip logic: if `test_types` is provided and a phase key is not in the list, skip that phase.
- Phase keys: `"qa"`, `"functional"`, `"ada"`, `"seo"`, `"performance"`.
- When `test_types` is `None` or empty: run all phases (existing behavior preserved).

---

## Data Flow

```
User checks boxes in Customize tab
  → frontend collects list of checked keys e.g. ["qa", "seo"]
  → POST /api/runs/start?project_id=X&test_mode=ai&test_types=qa&test_types=seo
  → runs.py extracts test_types, passes to Celery
  → qa_tasks.py skips phases not in list
  → run completes with only selected phases executed
```

---

## Test Type Key Mapping

| Checkbox label | Key passed | Phase skipped when absent |
|---|---|---|
| QA Test | `qa` | compare phase (visual AI) |
| Functionality Test | `functional` | functional checks |
| ADA Test | `ada` | accessibility checks |
| SEO Test | `seo` | SEO engine |
| Performance Test | `performance` | performance engine |

---

## UI Behavior

- **Default state**: Full QA tab active, all existing behavior unchanged.
- **Switching to Customize**: All 5 checkboxes pre-checked. User can uncheck any.
- **0 checkboxes checked**: "Run Selected Tests" button is disabled (grayed out, `disabled` attribute).
- **Switching back to Full QA**: `test_types` not sent — all phases run.
- **Testing mode** (AI Analysis Only / Design Comparison) appears in **both** tabs identically.

---

## Out of Scope

- Persisting checkbox state across sessions.
- Per-page test type selection.
- UI on the run results page showing which tests were run (future).
