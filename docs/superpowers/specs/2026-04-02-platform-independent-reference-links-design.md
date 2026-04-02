# Platform-Independent Reference Links

**Date:** 2026-04-02
**Status:** Approved

## Goal

Make the app accept any URL as a design reference (Vercel, Webflow, static HTML, etc.) instead of only Framer/Figma links. All URLs are treated as generic web pages screenshotted via Playwright, with Figma kept as a special case requiring API access.

## Decisions

- **Generic browser-based handling** for all reference URLs (no platform-specific logic except Figma)
- **Auto-detect platform** from the URL — no manual dropdown
- **Keep Figma as special case** — detected by `figma.com/` in URL, uses Figma API + token
- **Remove password support** for reference sites (drop `framer_password`)
- **Browser-based discovery** for all generic URLs (existing crawl logic already works for any site)
- **Existing `framer` rows** remain valid — treated as generic websites at runtime

## Changes

### 1. Database & Model

**File:** `backend/app/models/project.py`

- Add `website = "website"` to `SourceType` enum
- Remove `framer_password` column

**Migration:**

- Add `website` value to the `sourcetype` PostgreSQL enum
- Drop `framer_password` column

### 2. Auto-Detection Utility

**New file:** `backend/app/utils/source_detect.py`

```python
def detect_source_type(url: str | None) -> SourceType:
    if not url or not url.strip():
        return SourceType.none
    if "figma.com/" in url:
        return SourceType.figma
    return SourceType.website

def extract_figma_file_key(url: str) -> str | None:
    match = re.match(r"https?://(?:www\.)?figma\.com/(?:design|file)/([a-zA-Z0-9]+)", url)
    return match.group(1) if match else None
```

### 3. API Schema

**File:** `backend/app/schemas/project.py`

- `ProjectCreate`: remove `source_type` field, remove `framer_password` field
- `ProjectUpdate`: remove `framer_password` field
- `ProjectResponse`: keep `source_type` (read-only, auto-derived)

### 4. Router

**File:** `backend/app/routers/projects.py`

- `create_project`: call `detect_source_type(payload.source_url)` to set `source_type`
- `update_project`: re-derive `source_type` when `source_url` changes
- `discover_project`: use `discover_source_pages()` for `website` and `framer` types, Figma API for `figma`

### 5. Discovery Engine

**File:** `backend/app/engines/discovery_engine.py`

- Rename `discover_framer_pages()` → `discover_source_pages()` (code is already generic)

### 6. QA Tasks

**File:** `backend/app/workers/qa_tasks.py`

**Phase 1 (Discovery):**
- `website` or `framer` → `discover_source_pages(source_url)`
- `figma` → `FigmaCapture.list_frames(file_key)` then `auto_map()`

**Phase 2 (Capture):**
- `website` or `framer` → existing Playwright `capture_engine.capture_page()` (remove `password=project.framer_password`)
- `figma` → `FigmaCapture.capture_frames()` via API, store as `CaptureSource.design`

### 7. Frontend

**File:** `frontend/src/components/projects/ProjectForm.tsx`

- Remove `source_type` dropdown
- Always show optional "Reference URL" field with hint: "Paste any live site URL or Figma design link"
- Show `figma_token` field only when URL contains `figma.com/`
- Remove `framer_password` from form
- Remove `source_type` from submitted data

### What's NOT Changing

- `capture_engine.py` — already generic Playwright-based
- `comparison_engine.py` — already generic
- `figma_capture.py` — already exists, just gets wired up
- All other engines — untouched
- Existing `framer` database rows — still valid, treated as `website` at runtime
