# Per-Page Reference URLs for Design Comparison

**Date:** 2026-04-03  
**Status:** Approved

## Problem

When running a multi-page Design Comparison, the system constructs the reference URL by appending the Shopify page path to `project.source_url`:

```python
source_url = (project.source_url or "").rstrip("/") + source_path
```

If the reference site (Vercel, Framer, etc.) does not have collection pages, product pages, or other non-homepage paths accessible via that URL pattern, the design capture either fails or compares against a wrong/404 page, producing inaccurate results.

## Solution

Add a per-page mode toggle to the Run QA modal for non-homepage pages when Design Comparison is the global test mode. Users choose "Design Comparison" (requires a reference URL for that page) or "AI Only" per page. The Start button is hard-blocked until every page in "Design Comparison" mode has a reference URL.

## Architecture

### Frontend — `RunQAModal.tsx`

**Data model change:**

```ts
interface PageEntry {
  label: string;
  enabled: boolean;
  urls: string;
  pageMode: "design" | "ai";  // NEW — per-page mode
  referenceUrl: string;        // NEW — required when pageMode === "design" and global testMode === "design"
}
```

`DEFAULT_PAGES` updated to include `pageMode: "design"` and `referenceUrl: ""` on all entries.

**UI — per-page toggle:**

Rendered when: `testMode === "design"` AND `page.enabled === true` AND `page.label !== "Homepage"`.

Layout within the page card (below existing URLs textarea):
```
Mode:  [Design Comparison] [AI Only]   ← two-button toggle, default = Design Comparison

(when Design Comparison selected)
Reference URL *
[ https://live-site.com/collections/... ]
```

Homepage never shows the toggle — it always uses `project.source_url`.

**Validation:**

- `canStart` is false if any enabled non-homepage page has `pageMode === "design"` but `referenceUrl.trim() === ""`
- Error banner displays above the Start button: _"Design Comparison requires a reference URL for: [page names]"_

**`handleConfirm` changes:**

Builds a `pageReferenceUrls` record (only entries where `pageMode === "design"`).

**V1 rule: one reference URL per page category.** If a user enters multiple URLs in one page entry's textarea (e.g., 3 collection URLs), all resulting paths share the same `referenceUrl`. This is intentional for V1 simplicity.

Path extraction reuses the same per-line parsing logic already in `collectPagePaths` — applied per-entry rather than across all entries:

```ts
const pageReferenceUrls: Record<string, string> = {};
for (const page of pages) {
  if (!page.enabled || page.label === "Homepage" || page.pageMode !== "design") continue;
  // Extract paths from this entry's urls textarea (same logic as collectPagePaths)
  const lines = page.urls.split("\n").map((l) => l.trim()).filter(Boolean);
  const paths: string[] = lines.length === 0
    ? [defaultPathForLabel(page.label)]  // e.g. "/collections" for Collection Pages
    : lines.map((line) => { /* parse URL or path */ });
  for (const path of paths) {
    pageReferenceUrls[path] = page.referenceUrl.trim();
  }
}
```

Passes `pageReferenceUrls` to `onConfirm`.

**`onConfirm` prop signature change:**

```ts
interface RunQAModalProps {
  onConfirm: (
    pages: string,
    testMode: "design" | "ai",
    testTypes?: string[],
    pageReferenceUrls?: Record<string, string>
  ) => void;
  ...
}
```

### Frontend — `api/runs.ts`

`startRun` accepts an optional `pageReferenceUrls` parameter and sends it as a JSON body:

```ts
export const startRun = (
  projectId: number,
  pages?: string,
  testMode: "design" | "ai" = "design",
  testTypes?: string[],
  pageReferenceUrls?: Record<string, string>
) => {
  const params = new URLSearchParams();
  if (pages) params.set("pages", pages);
  if (testMode !== "design") params.set("test_mode", testMode);
  if (testTypes?.length) testTypes.forEach((t) => params.append("test_types", t));
  const qs = params.toString() ? `?${params.toString()}` : "";
  const body = pageReferenceUrls && Object.keys(pageReferenceUrls).length > 0
    ? { page_reference_urls: pageReferenceUrls }
    : undefined;
  return api.post(`/api/projects/${projectId}/runs${qs}`, body);
};
```

### Frontend — `ProjectDetailPage.tsx`

`runMutation.mutationFn` updated to pass `pageReferenceUrls` through from the modal's `onConfirm`.

### Backend — `routers/runs.py`

Add optional Pydantic request body:

```python
class StartRunBody(BaseModel):
    page_reference_urls: dict[str, str] | None = None
```

`start_run` endpoint signature gains:
```python
body: StartRunBody = Body(default_factory=StartRunBody)
```

Pass `page_reference_urls` to `_dispatch_qa_task` and on to the Celery task.

### Backend — `workers/qa_tasks.py`

`run_qa_job` and `_run_qa_job_async` accept:
```python
page_reference_urls: Optional[dict[str, str]] = None
```

**Capture phase — per-page reference URL logic:**

Replace the current global `source_url` construction with per-page logic:

```python
for shopify_path, source_path in page_mappings.items():
    is_homepage = shopify_path in ("/", "")
    
    # Determine reference URL for this page
    if skip_design:
        # global AI-only or no design source — existing path unchanged
        page_skip_design = True
        page_source_url = None
    elif is_homepage:
        # Homepage always uses project.source_url (existing behaviour)
        page_skip_design = False
        page_source_url = (project.source_url or "").rstrip("/") + source_path
    elif page_reference_urls and shopify_path in page_reference_urls:
        # Non-homepage with explicit reference URL
        page_skip_design = False
        page_source_url = page_reference_urls[shopify_path]
    else:
        # Non-homepage, no reference URL provided → AI-only for this page
        page_skip_design = True
        page_source_url = None
    
    # Rest of capture logic uses page_skip_design and page_source_url
    # instead of the global skip_design and constructed source_url
```

No database schema changes required. Reference URLs are ephemeral per-run inputs.

## Validation Rules

| Condition | Result |
|-----------|--------|
| Global mode = AI | No per-page toggle shown; all pages use AI |
| Homepage + Design mode | No toggle; uses `project.source_url` |
| Non-homepage + enabled + Design mode + referenceUrl provided | Design comparison with provided URL |
| Non-homepage + enabled + Design mode + referenceUrl empty | Start button blocked; error banner |
| Non-homepage + enabled + AI mode (per-page toggle) | AI-only for that page; no URL needed |

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/runs/RunQAModal.tsx` | Per-page toggle + referenceUrl field + validation |
| `frontend/src/api/runs.ts` | Add `pageReferenceUrls` param; send as JSON body |
| `frontend/src/pages/ProjectDetailPage.tsx` | Pass `pageReferenceUrls` through `runMutation` |
| `backend/app/routers/runs.py` | `StartRunBody` model; pass to task |
| `backend/app/workers/qa_tasks.py` | Per-page reference URL logic in capture phase |

## Out of Scope

- Storing per-page reference URLs persistently on the project (future feature)
- Full QA mode (all-pages discovery) — no change needed; reference URL logic is not applicable
