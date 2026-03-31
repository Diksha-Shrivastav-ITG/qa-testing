# Design: Website Source Type for Custom/Static Design References

**Date:** 2026-03-31
**Status:** Approved

## Problem

Currently the QA tool supports Framer and Figma as design source types for comparison testing. Users who host their design reference on custom/static websites (e.g., Netlify, Vercel, GitHub Pages) cannot use these for visual comparison. They need a way to provide individual page URLs from any website as design references.

## Solution

Add `website` as a new `SourceType` enum value. When selected, the user manually maps each Shopify page to a full design URL. These mappings are stored in `project.config["page_mappings"]` and used directly during QA runs — no auto-discovery needed.

## Changes Required

### 1. Backend Model — `SourceType` enum

**File:** `backend/app/models/project.py`

Add `website = "website"` to the `SourceType` enum.

### 2. DB Migration

Alembic migration to add `'website'` to the PostgreSQL `sourcetype` enum type.

### 3. Backend Schemas

**File:** `backend/app/schemas/project.py`

Add `page_mappings: Optional[dict[str, str]] = None` to `ProjectCreate` and `ProjectUpdate`. This is a dict of `{shopify_path: full_design_url}`.

### 4. Backend API — Project Creation

**File:** `backend/app/routers/projects.py`

On create, if `payload.page_mappings` is provided, store it in `project.config["page_mappings"]`. Same for update.

### 5. Backend QA Task — Discovery Phase

**File:** `backend/app/workers/qa_tasks.py`

No changes needed. The existing logic already checks `project.config.get("page_mappings", {})` first and skips discovery if mappings exist (line 240).

Since `website` projects have mappings pre-populated at creation time, discovery is automatically skipped.

### 6. Backend QA Task — Capture Phase

**File:** `backend/app/workers/qa_tasks.py`

Currently the design source URL is built as:
```python
source_url = (project.source_url or "").rstrip("/") + source_path
```

For `website` type, the mapping value IS the full URL. Change to:
```python
if project.source_type == SourceType.website:
    source_url = source_path  # full URL stored directly in mapping
else:
    source_url = (project.source_url or "").rstrip("/") + source_path
```

`has_design_source` check also needs updating to recognize `website` type:
```python
has_design_source = (
    project.source_type == SourceType.website  # website has full URLs in mappings
    or (
        project.source_url
        and project.source_url.strip()
        and project.source_type != SourceType.none
    )
)
```

### 7. Backend — Discovery Endpoint

**File:** `backend/app/routers/projects.py`

The `discover_project` endpoint needs a `website` branch. Since website mappings are manual, this endpoint should return the existing stored mappings instead of running browser discovery.

### 8. Frontend — ProjectForm

**File:** `frontend/src/components/projects/ProjectForm.tsx`

When `source_type === "website"`:
- Hide the single "Source URL" input
- Show a repeatable row form:
  - Each row: Shopify Page path (text, e.g. `/`) + Design URL (url, e.g. `https://...index.html`) + delete button
  - "+ Add Page" button to add rows
  - Start with one empty row
- On submit, convert rows into `page_mappings` object: `{"/": "https://...index.html", "/collections": "https://...collection.html"}`
- Send `page_mappings` as part of the form data

Dropdown option label: **"Website"** with helper text: *"Custom website — provide individual page URLs"*

### 9. Frontend — ProjectCard / ProjectDetail

Show "Website" as the source type label where Framer/Figma currently display.

## Data Flow

```
1. User creates project → source_type="website"
2. User adds rows: "/" → "https://example.netlify.app/index.html", etc.
3. Saved to project.config["page_mappings"] = {"/": "https://...", ...}
4. No source_url stored (not needed)

5. QA run starts
6. page_mappings found in config → discovery skipped
7. Capture phase: for each mapping, capture Shopify page + design URL
   - Design URL used as-is (full URL from mapping value)
8. Compare phase: screenshot vs screenshot (same as Framer)
9. All other phases (functional, ADA, link audit, SEO) run normally on Shopify pages
```

## Out of Scope

- Auto-discovery of pages on custom websites
- Password protection for custom websites (can be added later)
- Editing mappings after project creation (existing `/mappings` PUT endpoint already supports this)
