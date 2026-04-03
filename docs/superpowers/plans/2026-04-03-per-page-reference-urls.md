# Per-Page Reference URLs for Design Comparison — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to provide a separate reference URL per non-homepage page when running Design Comparison, so the system can capture the correct reference page instead of guessing from `project.source_url + path`.

**Architecture:** The RunQAModal gains a per-page mode toggle (Design Comparison / AI Only) for non-homepage pages. When "Design Comparison" is chosen, a required reference URL field appears. The frontend sends a `page_reference_urls` dict as a JSON body with the run request. The backend captures the exact URL provided instead of constructing it, and falls back to AI-only for any non-homepage page with no entry in the dict.

**Tech Stack:** React + TypeScript (frontend), FastAPI + Pydantic (backend API), Python asyncio + SQLAlchemy (background task), pytest (backend tests)

---

## File Map

| File | What changes |
|------|-------------|
| `frontend/src/components/runs/RunQAModal.tsx` | `PageEntry` interface, `DEFAULT_PAGES`, new state handlers, per-page toggle UI, validation, `handleConfirm`, `onConfirm` prop signature |
| `frontend/src/api/runs.ts` | `startRun` gains `pageReferenceUrls` param; sends JSON body |
| `frontend/src/pages/ProjectDetailPage.tsx` | `runMutation` and `onConfirm` pass `pageReferenceUrls` through |
| `backend/app/routers/runs.py` | `StartRunBody` Pydantic model; `start_run` endpoint accepts body; `_dispatch_qa_task` gains param |
| `backend/app/workers/qa_tasks.py` | `run_qa_job` and `_run_qa_job_async` accept `page_reference_urls`; capture loop uses per-page URL logic |
| `backend/tests/test_qa_tasks.py` | Two new tests: provided URL used for non-homepage; missing URL → AI-only for that page |

---

### Task 1: Update `PageEntry` interface and `DEFAULT_PAGES` in RunQAModal

**Files:**
- Modify: `frontend/src/components/runs/RunQAModal.tsx:3-14`

- [ ] **Step 1: Update the `PageEntry` interface**

Open `frontend/src/components/runs/RunQAModal.tsx`. Replace lines 3–7:

```ts
interface PageEntry {
  label: string;
  enabled: boolean;
  urls: string;
  pageMode: "design" | "ai";
  referenceUrl: string;
}
```

- [ ] **Step 2: Update `DEFAULT_PAGES`**

Replace lines 9–14:

```ts
const DEFAULT_PAGES: PageEntry[] = [
  { label: "Homepage", enabled: true, urls: "/", pageMode: "design", referenceUrl: "" },
  { label: "Collection Pages", enabled: false, urls: "", pageMode: "design", referenceUrl: "" },
  { label: "Product Pages", enabled: false, urls: "", pageMode: "design", referenceUrl: "" },
  { label: "Other Pages", enabled: false, urls: "", pageMode: "design", referenceUrl: "" },
];
```

- [ ] **Step 3: Add new state handlers inside the `RunQAModal` component body**

Add these two functions after the existing `updateUrls` handler (currently at line ~125):

```ts
const togglePageMode = (idx: number, mode: "design" | "ai") => {
  setPages((prev) => prev.map((p, i) => (i === idx ? { ...p, pageMode: mode } : p)));
};

const updateReferenceUrl = (idx: number, value: string) => {
  setPages((prev) => prev.map((p, i) => (i === idx ? { ...p, referenceUrl: value } : p)));
};
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/runs/RunQAModal.tsx
git commit -m "feat: add pageMode and referenceUrl fields to PageEntry"
```

---

### Task 2: Add per-page toggle + reference URL input UI

**Files:**
- Modify: `frontend/src/components/runs/RunQAModal.tsx` — inside `renderPageSelector`

The per-page toggle renders inside each non-homepage page card, below the existing URLs textarea, but only when:
- `!fullQA` (specific page mode)
- `page.enabled === true`
- `page.label !== "Homepage"`
- `testMode === "design"`

- [ ] **Step 1: Add toggle + reference URL input after the existing URLs textarea**

In `renderPageSelector`, find this block (around line 207):
```tsx
{!fullQA && page.enabled && (
  <div className="px-3 pb-3">
    ...textarea for urls...
  </div>
)}
```

Replace it with:

```tsx
{!fullQA && page.enabled && (
  <div className="px-3 pb-3 space-y-2">
    {/* Existing URLs textarea */}
    <div>
      <label htmlFor={`urls-${idx}`} className="sr-only">
        {page.label} URLs
      </label>
      <textarea
        id={`urls-${idx}`}
        value={page.urls}
        onChange={(e) => updateUrls(idx, e.target.value)}
        rows={2}
        placeholder={
          page.label === "Homepage"
            ? "/ (default — or paste a specific URL)"
            : page.label === "Collection Pages"
            ? "Paste collection URLs — one per line:\nhttps://store.com/collections/summer"
            : page.label === "Product Pages"
            ? "Paste product URLs — one per line:\nhttps://store.com/products/boot-1"
            : "Paste page URLs:\nhttps://store.com/pages/about"
        }
        className="w-full px-2.5 py-1.5 border border-gray-200 dark:border-slate-600 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500"
      />
    </div>

    {/* Per-page mode toggle — only for non-homepage pages in design mode */}
    {page.label !== "Homepage" && testMode === "design" && (
      <div className="space-y-1.5">
        <p className="text-xs text-gray-500 dark:text-slate-400 font-medium">
          Comparison mode
        </p>
        <div className="flex rounded-md overflow-hidden border border-gray-200 dark:border-slate-600">
          <button
            type="button"
            onClick={() => togglePageMode(idx, "design")}
            className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
              page.pageMode === "design"
                ? "bg-indigo-600 text-white"
                : "bg-white dark:bg-slate-800 text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-white/5"
            }`}
          >
            Design Comparison
          </button>
          <button
            type="button"
            onClick={() => togglePageMode(idx, "ai")}
            className={`flex-1 py-1.5 text-xs font-medium border-l border-gray-200 dark:border-slate-600 transition-colors ${
              page.pageMode === "ai"
                ? "bg-indigo-600 text-white"
                : "bg-white dark:bg-slate-800 text-gray-500 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-white/5"
            }`}
          >
            AI Only
          </button>
        </div>

        {/* Reference URL — required when Design Comparison selected */}
        {page.pageMode === "design" && (
          <div>
            <label
              htmlFor={`ref-url-${idx}`}
              className="text-xs text-gray-500 dark:text-slate-400 mb-1 block"
            >
              Reference URL <span className="text-red-500" aria-hidden="true">*</span>
            </label>
            <input
              id={`ref-url-${idx}`}
              type="url"
              value={page.referenceUrl}
              onChange={(e) => updateReferenceUrl(idx, e.target.value)}
              placeholder="https://live-site.com/collections/..."
              className="w-full px-2.5 py-1.5 border border-gray-200 dark:border-slate-600 rounded-md text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400 bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500"
            />
          </div>
        )}
      </div>
    )}
  </div>
)}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/runs/RunQAModal.tsx
git commit -m "feat: add per-page design/AI toggle and reference URL input"
```

---

### Task 3: Add validation + error banner

**Files:**
- Modify: `frontend/src/components/runs/RunQAModal.tsx` — `canStart` logic + banner

- [ ] **Step 1: Compute `pagesNeedingRef` in the component body**

Find this line in the component body (around line 159):
```ts
const anyEnabled = fullQA || pages.some((p) => p.enabled);
const canStart = !isLoading && anyEnabled && (modalTab === "full" || selectedTests.size > 0);
```

Replace with:

```ts
const anyEnabled = fullQA || pages.some((p) => p.enabled);

// Non-homepage pages in Design Comparison mode that are missing a reference URL
const pagesNeedingRef =
  !fullQA && testMode === "design"
    ? pages.filter(
        (p) =>
          p.enabled &&
          p.label !== "Homepage" &&
          p.pageMode === "design" &&
          !p.referenceUrl.trim()
      )
    : [];

const canStart =
  !isLoading &&
  anyEnabled &&
  (modalTab === "full" || selectedTests.size > 0) &&
  pagesNeedingRef.length === 0;
```

- [ ] **Step 2: Add the error banner in the Actions section**

Find the Actions `<div>` near the bottom of the modal (around line 420):
```tsx
{/* Actions */}
<div className="flex gap-3 pt-1">
  <button onClick={handleConfirm} ...>
```

Add the banner **above** the button:

```tsx
{/* Actions */}
<div className="space-y-3">
  {pagesNeedingRef.length > 0 && (
    <div
      role="alert"
      className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg px-3 py-2 text-xs text-red-700 dark:text-red-400"
    >
      Design Comparison requires a reference URL for:{" "}
      <span className="font-semibold">
        {pagesNeedingRef.map((p) => p.label).join(", ")}
      </span>
    </div>
  )}
  <div className="flex gap-3">
    <button
      onClick={handleConfirm}
      disabled={!canStart}
      className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
    >
      {isLoading
        ? "Starting..."
        : modalTab === "customize"
        ? <><span aria-hidden="true">⚙️</span> Run Selected Tests</>
        : <><span aria-hidden="true">🚀</span> Start QA Run</>}
    </button>
    <button
      onClick={onCancel}
      disabled={isLoading}
      className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-slate-300 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
    >
      Cancel
    </button>
  </div>
</div>
```

Note: the existing closing `</div>` for the modal wrapper must still be present. Remove the old `<div className="flex gap-3 pt-1">` and its matching `</div>` and replace with the block above.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/runs/RunQAModal.tsx
git commit -m "feat: block run start when reference URLs are missing"
```

---

### Task 4: Update `handleConfirm` and `onConfirm` prop signature

**Files:**
- Modify: `frontend/src/components/runs/RunQAModal.tsx`

- [ ] **Step 1: Update `onConfirm` prop type in `RunQAModalProps`**

Find (around line 39):
```ts
interface RunQAModalProps {
  onConfirm: (pages: string, testMode: "design" | "ai", testTypes?: string[]) => void;
  onCancel: () => void;
  isLoading: boolean;
  hasDesignSource?: boolean;
}
```

Replace with:
```ts
interface RunQAModalProps {
  onConfirm: (
    pages: string,
    testMode: "design" | "ai",
    testTypes?: string[],
    pageReferenceUrls?: Record<string, string>
  ) => void;
  onCancel: () => void;
  isLoading: boolean;
  hasDesignSource?: boolean;
}
```

- [ ] **Step 2: Rewrite `handleConfirm`**

Find (around line 150):
```ts
const handleConfirm = () => {
  const pageArg = collectPagePaths(fullQA, pages);
  if (modalTab === "full") {
    onConfirm(pageArg, testMode, undefined);
  } else {
    onConfirm(pageArg, testMode, Array.from(selectedTests));
  }
};
```

Replace with:
```ts
const handleConfirm = () => {
  const pageArg = collectPagePaths(fullQA, pages);

  // Build per-page reference URLs dict.
  // One reference URL per page category — all paths derived from a category entry
  // share the same reference URL (V1 design decision).
  const pageReferenceUrls: Record<string, string> = {};
  if (!fullQA && testMode === "design") {
    for (const page of pages) {
      if (!page.enabled || page.label === "Homepage" || page.pageMode !== "design") continue;
      const refUrl = page.referenceUrl.trim();
      if (!refUrl) continue;

      // Extract paths from this page entry's URLs textarea
      const lines = page.urls.split("\n").map((l) => l.trim()).filter(Boolean);
      if (lines.length === 0) {
        // No URLs entered — use category default path
        const defaultPath =
          page.label === "Collection Pages" ? "/collections"
          : page.label === "Product Pages" ? "/products"
          : null; // "Other Pages" has no single default path — skip
        if (defaultPath) pageReferenceUrls[defaultPath] = refUrl;
      } else {
        for (const line of lines) {
          let path: string;
          try {
            path = new URL(line).pathname;
          } catch {
            path = line.startsWith("/") ? line : `/${line}`;
          }
          pageReferenceUrls[path] = refUrl;
        }
      }
    }
  }

  if (modalTab === "full") {
    onConfirm(pageArg, testMode, undefined, pageReferenceUrls);
  } else {
    onConfirm(pageArg, testMode, Array.from(selectedTests), pageReferenceUrls);
  }
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/runs/RunQAModal.tsx
git commit -m "feat: collect pageReferenceUrls in handleConfirm and extend onConfirm signature"
```

---

### Task 5: Update `ProjectDetailPage.tsx` to pass `pageReferenceUrls`

**Files:**
- Modify: `frontend/src/pages/ProjectDetailPage.tsx:73-81` (runMutation) and `:431-433` (RunQAModal usage)

- [ ] **Step 1: Update `runMutation`**

Find (around line 73):
```ts
const runMutation = useMutation({
  mutationFn: ({ pages, testMode, testTypes }: { pages: string; testMode: "design" | "ai"; testTypes?: string[] }) =>
    startRun(projectId, pages || undefined, testMode, testTypes),
  onSuccess: (res) => {
    queryClient.invalidateQueries({ queryKey: ["runs", projectId] });
    setShowRunModal(false);
    navigate(`/runs/${res.data.id}`);
  },
});
```

Replace with:
```ts
const runMutation = useMutation({
  mutationFn: ({
    pages,
    testMode,
    testTypes,
    pageReferenceUrls,
  }: {
    pages: string;
    testMode: "design" | "ai";
    testTypes?: string[];
    pageReferenceUrls?: Record<string, string>;
  }) => startRun(projectId, pages || undefined, testMode, testTypes, pageReferenceUrls),
  onSuccess: (res) => {
    queryClient.invalidateQueries({ queryKey: ["runs", projectId] });
    setShowRunModal(false);
    navigate(`/runs/${res.data.id}`);
  },
});
```

- [ ] **Step 2: Update the `RunQAModal` `onConfirm` callback**

Find (around line 431):
```tsx
<RunQAModal
  onConfirm={(pages, testMode, testTypes) =>
    runMutation.mutate({ pages, testMode, testTypes })
  }
```

Replace with:
```tsx
<RunQAModal
  onConfirm={(pages, testMode, testTypes, pageReferenceUrls) =>
    runMutation.mutate({ pages, testMode, testTypes, pageReferenceUrls })
  }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectDetailPage.tsx
git commit -m "feat: pass pageReferenceUrls through ProjectDetailPage to startRun"
```

---

### Task 6: Update `api/runs.ts` to send `pageReferenceUrls` as JSON body

**Files:**
- Modify: `frontend/src/api/runs.ts:3-17`

- [ ] **Step 1: Update `startRun`**

Replace the entire `startRun` function:

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
  if (testTypes && testTypes.length > 0) {
    testTypes.forEach((t) => params.append("test_types", t));
  }
  const qs = params.toString() ? `?${params.toString()}` : "";
  const body =
    pageReferenceUrls && Object.keys(pageReferenceUrls).length > 0
      ? { page_reference_urls: pageReferenceUrls }
      : undefined;
  return api.post(`/api/projects/${projectId}/runs${qs}`, body);
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/runs.ts
git commit -m "feat: send pageReferenceUrls as JSON body in startRun"
```

---

### Task 7: [TDD] Backend — `StartRunBody` in `runs.py`

**Files:**
- Modify: `backend/app/routers/runs.py`

No dedicated test file for this task — the qa_tasks tests in Task 8 cover the end-to-end behavior. We validate here by inspecting the Celery task call.

- [ ] **Step 1: Add `StartRunBody` Pydantic model**

At the top of `backend/app/routers/runs.py`, after the existing imports add:

```python
from fastapi import Body
from pydantic import BaseModel as PydanticBaseModel


class StartRunBody(PydanticBaseModel):
    page_reference_urls: dict[str, str] | None = None
```

- [ ] **Step 2: Update `_dispatch_qa_task` to accept and forward `page_reference_urls`**

Find (around line 30):
```python
def _dispatch_qa_task(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    test_mode: str = "design",
    test_types: Optional[list[str]] = None,
) -> None:
    """Dispatch the Celery QA task. Silently swallows errors (e.g. no broker)."""
    try:
        from app.workers.qa_tasks import run_qa_job

        run_qa_job.delay(run_id, partial_pages, test_mode, test_types)
    except Exception:
        pass
```

Replace with:
```python
def _dispatch_qa_task(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    test_mode: str = "design",
    test_types: Optional[list[str]] = None,
    page_reference_urls: Optional[dict[str, str]] = None,
) -> None:
    """Dispatch the Celery QA task. Silently swallows errors (e.g. no broker)."""
    try:
        from app.workers.qa_tasks import run_qa_job

        run_qa_job.delay(run_id, partial_pages, test_mode, test_types, page_reference_urls)
    except Exception:
        pass
```

- [ ] **Step 3: Update the `start_run` endpoint to accept a JSON body and pass it through**

Find (around line 67):
```python
@router.post(
    "/api/projects/{project_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_run(
    project_id: int,
    partial: bool = Query(default=False),
    pages: Optional[str] = Query(default=None, description="Comma-separated page slugs"),
    test_mode: str = Query(default="design", description="'design' = compare vs Framer/Figma, 'ai' = AI-only analysis"),
    test_types: Optional[list[str]] = Query(default=None, description="Which test phases to run: qa, functional, ada, seo, performance"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "developer")),
) -> RunResponse:
```

Replace the signature with:
```python
@router.post(
    "/api/projects/{project_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_run(
    project_id: int,
    partial: bool = Query(default=False),
    pages: Optional[str] = Query(default=None, description="Comma-separated page slugs"),
    test_mode: str = Query(default="design", description="'design' = compare vs Framer/Figma, 'ai' = AI-only analysis"),
    test_types: Optional[list[str]] = Query(default=None, description="Which test phases to run: qa, functional, ada, seo, performance"),
    body: StartRunBody = Body(default_factory=StartRunBody),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "developer")),
) -> RunResponse:
```

Then inside the function body, find this line (around line 111):
```python
    _dispatch_qa_task(run.id, partial_pages, test_mode, test_types)
```

Replace with:
```python
    _dispatch_qa_task(run.id, partial_pages, test_mode, test_types, body.page_reference_urls)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/runs.py
git commit -m "feat: accept page_reference_urls JSON body in start_run endpoint"
```

---

### Task 8: [TDD] Backend — per-page capture logic in `qa_tasks.py`

**Files:**
- Modify: `backend/app/workers/qa_tasks.py`
- Modify: `backend/tests/test_qa_tasks.py`

- [ ] **Step 1: Write the two failing tests**

Open `backend/tests/test_qa_tasks.py` and add these tests at the end of the file:

```python
@patch(_PATCHES["func"])
@patch(_PATCHES["comp"])
@patch(_PATCHES["cap"])
@patch(_PATCHES["sf"])
def test_per_page_reference_url_is_used_for_non_homepage(
    mock_sf, mock_cap_cls, mock_comp_cls, mock_func_cls, db
):
    """When page_reference_urls contains an entry for a non-homepage path,
    the design capture uses that URL directly instead of project.source_url + path."""
    project, run = _seed_project_and_run(
        db,
        config={"page_mappings": {"/": "/", "/collections/summer": "/collections/summer"}},
    )
    mock_sf.return_value = lambda: _TestSessionLocal()

    captured_urls: list[tuple[str, str]] = []  # (source, url)

    mock_capture = MagicMock()

    async def _fake_capture(url, page_name, run_dir, source, breakpoints, password=None, **kw):
        captured_urls.append((source, url))
        return [_make_capture_result(page_name, bp, source) for bp in breakpoints]

    mock_capture.capture_page = AsyncMock(side_effect=_fake_capture)
    mock_cap_cls.return_value = mock_capture

    mock_comparison = MagicMock()

    async def _compare(design_path, shopify_path, output_dir, page, breakpoint):
        return _make_comparison_result(page, breakpoint)

    mock_comparison.compare = AsyncMock(side_effect=_compare)
    mock_comp_cls.return_value = mock_comparison

    mock_functional = MagicMock()
    mock_functional._create_page = AsyncMock(return_value=AsyncMock())
    mock_functional.run_surface_tests = AsyncMock(return_value=[])
    mock_functional.run_shopify_flows = AsyncMock(return_value=[])
    mock_func_cls.return_value = mock_functional

    noop_publish = MagicMock()

    from app.workers.qa_tasks import _run_qa_job_async

    _run_async(
        _run_qa_job_async(
            run.id,
            _publish_fn=noop_publish,
            page_reference_urls={
                "/collections/summer": "https://live-site.com/collections/summer"
            },
        )
    )

    design_urls = [url for source, url in captured_urls if source == "design"]
    # The reference URL provided must be used directly — NOT project.source_url + path
    assert any("live-site.com/collections/summer" in url for url in design_urls), (
        f"Expected live-site.com/collections/summer in design captures, got: {design_urls}"
    )
    # project.source_url is https://test.vercel.app — it must NOT appear for collections
    assert not any(
        "test.vercel.app/collections" in url for url in design_urls
    ), f"Wrongly used project.source_url for collections: {design_urls}"


@patch(_PATCHES["func"])
@patch(_PATCHES["comp"])
@patch(_PATCHES["cap"])
@patch(_PATCHES["sf"])
def test_non_homepage_without_reference_url_uses_ai_only(
    mock_sf, mock_cap_cls, mock_comp_cls, mock_func_cls, db
):
    """When a non-homepage path has no entry in page_reference_urls,
    that page is captured with shopify source only (AI-only mode)."""
    project, run = _seed_project_and_run(
        db,
        config={"page_mappings": {"/": "/", "/collections/summer": "/collections/summer"}},
    )
    mock_sf.return_value = lambda: _TestSessionLocal()

    captured_sources_by_page: dict[str, set[str]] = {}

    mock_capture = MagicMock()

    async def _fake_capture(url, page_name, run_dir, source, breakpoints, password=None, **kw):
        captured_sources_by_page.setdefault(page_name, set()).add(source)
        return [_make_capture_result(page_name, bp, source) for bp in breakpoints]

    mock_capture.capture_page = AsyncMock(side_effect=_fake_capture)
    mock_cap_cls.return_value = mock_capture

    mock_comparison = MagicMock()

    async def _compare_ai(shopify_path, output_dir, page, breakpoint):
        return _make_comparison_result(page, breakpoint, ssim=0.0)

    mock_comparison.compare_ai_only = AsyncMock(side_effect=_compare_ai)
    mock_comp_cls.return_value = mock_comparison

    mock_functional = MagicMock()
    mock_functional._create_page = AsyncMock(return_value=AsyncMock())
    mock_functional.run_surface_tests = AsyncMock(return_value=[])
    mock_functional.run_shopify_flows = AsyncMock(return_value=[])
    mock_func_cls.return_value = mock_functional

    noop_publish = MagicMock()

    from app.workers.qa_tasks import _run_qa_job_async

    _run_async(
        _run_qa_job_async(
            run.id,
            _publish_fn=noop_publish,
            page_reference_urls={},  # empty — no reference URL for /collections/summer
        )
    )

    # Homepage ("/") → page_name "home" — should have BOTH shopify and design captures
    assert "shopify" in captured_sources_by_page.get("home", set())
    assert "design" in captured_sources_by_page.get("home", set())

    # Collections page → page_name "collections/summer" — shopify only (no reference URL given)
    collections_page = "collections/summer"
    assert "shopify" in captured_sources_by_page.get(collections_page, set()), (
        f"Expected shopify capture for {collections_page}"
    )
    assert "design" not in captured_sources_by_page.get(collections_page, set()), (
        f"Unexpected design capture for {collections_page} — no reference URL was provided"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_qa_tasks.py::test_per_page_reference_url_is_used_for_non_homepage tests/test_qa_tasks.py::test_non_homepage_without_reference_url_uses_ai_only -v
```

Expected: Both tests FAIL — `_run_qa_job_async` does not accept `page_reference_urls` yet.

- [ ] **Step 3: Update `_run_qa_job_async` signature**

In `backend/app/workers/qa_tasks.py`, find (around line 171):

```python
async def _run_qa_job_async(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    test_mode: str = "design",
    test_types: Optional[list[str]] = None,
    *,
    _publish_fn=publish_progress,
) -> None:
```

Replace with:

```python
async def _run_qa_job_async(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    test_mode: str = "design",
    test_types: Optional[list[str]] = None,
    page_reference_urls: Optional[dict[str, str]] = None,
    *,
    _publish_fn=publish_progress,
) -> None:
```

- [ ] **Step 4: Update `run_qa_job` Celery task signature**

Find (around line 788):

```python
@celery_app.task(name="run_qa_job")
def run_qa_job(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    test_mode: str = "design",
    test_types: Optional[list[str]] = None,
) -> dict:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            _run_qa_job_async(run_id, partial_pages, test_mode, test_types=test_types)
        )
    finally:
        loop.close()
    return {"run_id": run_id, "status": "dispatched"}
```

Replace with:

```python
@celery_app.task(name="run_qa_job")
def run_qa_job(
    run_id: int,
    partial_pages: Optional[list[str]] = None,
    test_mode: str = "design",
    test_types: Optional[list[str]] = None,
    page_reference_urls: Optional[dict[str, str]] = None,
) -> dict:
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            _run_qa_job_async(
                run_id,
                partial_pages,
                test_mode,
                test_types=test_types,
                page_reference_urls=page_reference_urls,
            )
        )
    finally:
        loop.close()
    return {"run_id": run_id, "status": "dispatched"}
```

- [ ] **Step 5: Replace the per-page capture URL construction**

In `_run_qa_job_async`, inside the capture loop starting at line ~338, find this block:

```python
        if skip_design:
            shopify_results = await capture_engine.capture_page(
                url=shopify_url,
                page_name=page_name,
                run_dir=run_dir,
                source="shopify",
                breakpoints=BREAKPOINTS,
                password=project.shopify_password,
            )
            design_results = []
        else:
            # Capture Shopify + Design simultaneously
            source_url = (project.source_url or "").rstrip("/") + source_path
            shopify_results, design_results = await asyncio.gather(
                capture_engine.capture_page(
                    url=shopify_url,
                    page_name=page_name,
                    run_dir=run_dir,
                    source="shopify",
                    breakpoints=BREAKPOINTS,
                    password=project.shopify_password,
                ),
                capture_engine.capture_page(
                    url=source_url,
                    page_name=page_name,
                    run_dir=run_dir,
                    source="design",
                    breakpoints=BREAKPOINTS,
                ),
            )
```

Replace with:

```python
        # ---- Determine per-page reference URL and whether to skip design ----
        _is_homepage = shopify_path in ("/", "")
        if skip_design:
            # Global AI-only or no design source configured — never do design capture
            _page_skip_design = True
            _page_source_url = None
        elif _is_homepage:
            # Homepage always uses project.source_url (unchanged behaviour)
            _page_skip_design = False
            _page_source_url = (project.source_url or "").rstrip("/") + source_path
        elif page_reference_urls and shopify_path in page_reference_urls:
            # Non-homepage with an explicit reference URL provided by the user
            _page_skip_design = False
            _page_source_url = page_reference_urls[shopify_path]
        else:
            # Non-homepage with no reference URL → AI-only for this page
            _page_skip_design = True
            _page_source_url = None

        if _page_skip_design:
            shopify_results = await capture_engine.capture_page(
                url=shopify_url,
                page_name=page_name,
                run_dir=run_dir,
                source="shopify",
                breakpoints=BREAKPOINTS,
                password=project.shopify_password,
            )
            design_results = []
        else:
            # Capture Shopify + Design simultaneously
            shopify_results, design_results = await asyncio.gather(
                capture_engine.capture_page(
                    url=shopify_url,
                    page_name=page_name,
                    run_dir=run_dir,
                    source="shopify",
                    breakpoints=BREAKPOINTS,
                    password=project.shopify_password,
                ),
                capture_engine.capture_page(
                    url=_page_source_url,
                    page_name=page_name,
                    run_dir=run_dir,
                    source="design",
                    breakpoints=BREAKPOINTS,
                ),
            )
```

- [ ] **Step 6: Replace remaining `skip_design` references inside the capture loop with `_page_skip_design`**

After the capture calls, find two more uses of `skip_design` in the same loop body. They appear in the capture-pairs building block (around line 397):

```python
            if skip_design:
                for bp, sr in shopify_by_bp.items():
                    capture_pairs.append({
```

and:

```python
            else:
                for dr in design_results:
```

Replace both `skip_design` → `_page_skip_design` in those lines. The full block should look like:

```python
            shopify_by_bp = {r.breakpoint: r for r in shopify_results if r.status == "success"}

            if _page_skip_design:
                for bp, sr in shopify_by_bp.items():
                    capture_pairs.append({
                        "page": page_name,
                        "breakpoint": bp,
                        "shopify_path": sr.image_path,
                        "design_path": None,
                        "mode": "ai",
                    })
            else:
                for dr in design_results:
                    captured_count += 1
                    _publish_fn(
                        run_id, "capture", page=page_name,
                        breakpoint_val=dr.breakpoint,
                        progress=_overall_progress(done_phases, "capture", captured_count / total_captures),
                        message=f"Captured design {page_name} @{dr.breakpoint}px",
                    )
                    if dr.status == "success":
                        db.add(Capture(
                            qa_run_id=run_id,
                            source=CaptureSource.design,
                            page=page_name,
                            breakpoint=dr.breakpoint,
                            image_path=dr.image_path,
                        ))

                design_by_bp = {r.breakpoint: r for r in design_results if r.status == "success"}
                failed_design_bps = [r.breakpoint for r in design_results if r.status != "success"]
                if failed_design_bps:
                    logger.warning("Design capture failed for %s at breakpoints %s — falling back to AI-only", page_name, failed_design_bps)
                for bp in BREAKPOINTS:
                    if bp not in shopify_by_bp:
                        continue
                    if bp in design_by_bp:
                        capture_pairs.append({
                            "page": page_name,
                            "breakpoint": bp,
                            "shopify_path": shopify_by_bp[bp].image_path,
                            "design_path": design_by_bp[bp].image_path,
                            "mode": "design",
                        })
                    else:
                        # Design capture failed for this breakpoint — fall back to AI-only
                        capture_pairs.append({
                            "page": page_name,
                            "breakpoint": bp,
                            "shopify_path": shopify_by_bp[bp].image_path,
                            "design_path": None,
                            "mode": "ai",
                        })
```

- [ ] **Step 7: Run the new tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_qa_tasks.py::test_per_page_reference_url_is_used_for_non_homepage tests/test_qa_tasks.py::test_non_homepage_without_reference_url_uses_ai_only -v
```

Expected: Both PASS.

- [ ] **Step 8: Run the full test suite to ensure no regressions**

```bash
cd backend && python -m pytest tests/test_qa_tasks.py -v
```

Expected: All existing tests plus the two new ones PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/workers/qa_tasks.py backend/tests/test_qa_tasks.py
git commit -m "feat: use per-page reference URLs in capture phase; AI-only fallback for pages without reference URL"
```

---

## Done

All 8 tasks complete. The feature is implemented end-to-end:

1. The RunQAModal shows a Design Comparison / AI Only toggle per non-homepage page when design mode is active.
2. Selecting Design Comparison requires a reference URL — the Start button is blocked until it is filled.
3. The provided URL is sent to the backend as `page_reference_urls`.
4. The capture phase uses the exact URL provided, falling back to AI-only for any page without one.
