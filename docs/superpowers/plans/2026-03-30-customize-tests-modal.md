# Customize Tests Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "Test Cases" tab on ProjectDetailPage with a "Full QA | Customize" tab bar inside RunQAModal, and wire `test_types` through frontend → API → Celery → qa_tasks phase skipping.

**Architecture:** Frontend tab toggle in RunQAModal sends optional `test_types[]` query params. Backend skips phases not in the list. Link audit always runs (not user-configurable).

**Tech Stack:** React 19/TypeScript/Tailwind (frontend), FastAPI (backend), Celery (workers)

**Spec:** `docs/superpowers/specs/2026-03-30-customize-tests-modal-design.md`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `frontend/src/pages/ProjectDetailPage.tsx` | Modify | Remove Test Cases tab + update runMutation signature |
| `frontend/src/components/runs/RunQAModal.tsx` | Modify | Add Full QA/Customize tab bar + checkboxes |
| `frontend/src/api/runs.ts` | Modify | Add `testTypes?` param to `startRun` |
| `backend/app/routers/runs.py` | Modify | Accept `test_types` query param, pass to task |
| `backend/app/workers/qa_tasks.py` | Modify | Accept + apply `test_types` phase skipping |

---

## Task 1: Remove Test Cases tab from ProjectDetailPage

**Files:**
- Modify: `frontend/src/pages/ProjectDetailPage.tsx`

- [ ] **Step 1: Update the Tab type**

In `ProjectDetailPage.tsx` line 24, change:
```ts
type Tab = "runs" | "test-cases" | "settings";
```
to:
```ts
type Tab = "runs" | "settings";
```

- [ ] **Step 2: Remove TEST_CASES, enabledTests, toggleTest, testCategories**

Delete lines 26–79 (everything from `const TEST_CASES = [` through `const testCategories = ...`):
```ts
// DELETE these lines entirely:
const TEST_CASES = [ ... ];   // lines 26–40
// and inside ProjectDetailPage:
const [enabledTests, setEnabledTests] = useState<Set<string>>(
    () => new Set(TEST_CASES.filter(t => t.default).map(t => t.id))
);                             // lines 67–69
const toggleTest = (id: string) => { ... };  // lines 71–77
const testCategories = [...new Set(TEST_CASES.map(t => t.category))];  // line 79
```

- [ ] **Step 3: Remove Test Cases tab nav item**

In the tabs array (around line 191–195), remove the `{ key: "test-cases", label: "Test Cases" }` entry so only "Runs" and "Settings" remain:
```tsx
{([
  { key: "runs", label: "Runs" },
  { key: "settings", label: "Settings" },
] as { key: Tab; label: string }[]).map((tab) => (
```

- [ ] **Step 4: Remove Test Cases tab content block**

Delete the entire block (approx lines 277–344):
```tsx
// DELETE this entire block:
{/* Test Cases Tab */}
{activeTab === "test-cases" && (
  <div className="max-w-2xl">
    ...
  </div>
)}
```

- [ ] **Step 5: Update runMutation to accept testTypes**

Change the mutation definition (around line 101–109):
```tsx
const runMutation = useMutation({
  mutationFn: ({
    pages,
    testMode,
    testTypes,
  }: {
    pages: string;
    testMode: "design" | "ai";
    testTypes?: string[];
  }) => startRun(projectId, pages || undefined, testMode, testTypes),
  onSuccess: (res) => {
    queryClient.invalidateQueries({ queryKey: ["runs", projectId] });
    setShowRunModal(false);
    navigate(`/runs/${res.data.id}`);
  },
});
```

- [ ] **Step 6: Update RunQAModal onConfirm call**

Change the modal's onConfirm handler (near line 443):
```tsx
<RunQAModal
  onConfirm={(pages, testMode, testTypes) =>
    runMutation.mutate({ pages, testMode, testTypes })
  }
  onCancel={() => setShowRunModal(false)}
  isLoading={runMutation.isPending}
/>
```

- [ ] **Step 7: Verify TypeScript compiles**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/ProjectDetailPage.tsx
git commit -m "feat: remove Test Cases tab from ProjectDetailPage"
```

---

## Task 2: Add Full QA | Customize tab bar to RunQAModal

**Files:**
- Modify: `frontend/src/components/runs/RunQAModal.tsx`

- [ ] **Step 1: Update RunQAModalProps interface**

Change `onConfirm` signature to include optional `testTypes`:
```tsx
interface RunQAModalProps {
  onConfirm: (pages: string, testMode: "design" | "ai", testTypes?: string[]) => void;
  onCancel: () => void;
  isLoading: boolean;
}
```

- [ ] **Step 2: Add TEST_TYPES constant above the component**

Add after `TEST_MODES` (around line 29):
```tsx
const TEST_TYPES = [
  { key: "qa", label: "QA Test", desc: "Visual AI analysis & design comparison", icon: "🔍" },
  { key: "functional", label: "Functionality Test", desc: "Cart, checkout, search, mobile menu", icon: "⚡" },
  { key: "ada", label: "ADA Test", desc: "WCAG 2.1 accessibility compliance", icon: "♿" },
  { key: "seo", label: "SEO Test", desc: "GTM, GA4, GSC, Bing, meta tags", icon: "🔎" },
  { key: "performance", label: "Performance Test", desc: "Load time, TTFB, resource size", icon: "📊" },
];
```

- [ ] **Step 3: Add modal tab state and selectedTests state**

Inside `RunQAModal`, after the existing `testMode` state (around line 40):
```tsx
const [modalTab, setModalTab] = useState<"full" | "customize">("full");
const [selectedTests, setSelectedTests] = useState<Set<string>>(
  () => new Set(TEST_TYPES.map((t) => t.key))
);

const toggleTestType = (key: string) => {
  setSelectedTests((prev) => {
    const next = new Set(prev);
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  });
};
```

- [ ] **Step 4: Update handleConfirm to pass testTypes**

Replace the existing `handleConfirm` function body:
```tsx
const handleConfirm = () => {
  // Collect pages (existing logic unchanged)
  let pageArg = "";
  if (!fullQA) {
    const allPaths: string[] = [];
    for (const page of pages) {
      if (!page.enabled) continue;
      const lines = page.urls
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);
      if (lines.length === 0) {
        if (page.label === "Homepage") allPaths.push("/");
        else if (page.label === "Collection Pages") allPaths.push("/collections");
        else if (page.label === "Product Pages") allPaths.push("/products");
        else allPaths.push("__other__");
      } else {
        for (const line of lines) {
          try {
            const parsed = new URL(line);
            allPaths.push(parsed.pathname);
          } catch {
            allPaths.push(line.startsWith("/") ? line : `/${line}`);
          }
        }
      }
    }
    pageArg = allPaths.join(",");
  }

  // Pass testTypes only when in Customize tab
  const testTypes =
    modalTab === "customize" ? Array.from(selectedTests) : undefined;

  onConfirm(pageArg, testMode, testTypes);
};
```

- [ ] **Step 5: Add the Full QA | Customize tab bar to JSX**

In the modal body, after the title block (after `<p className="text-sm text-gray-500 mt-0.5">...</p>`), add the tab bar before the existing Full QA toggle:
```tsx
{/* Tab bar */}
<div className="flex border border-gray-200 rounded-lg overflow-hidden">
  <button
    type="button"
    onClick={() => setModalTab("full")}
    className={`flex-1 py-2 text-sm font-semibold transition-colors ${
      modalTab === "full"
        ? "bg-indigo-600 text-white"
        : "bg-gray-50 text-gray-500 hover:bg-gray-100"
    }`}
  >
    ⚡ Full QA
  </button>
  <button
    type="button"
    onClick={() => setModalTab("customize")}
    className={`flex-1 py-2 text-sm font-semibold border-l border-gray-200 transition-colors ${
      modalTab === "customize"
        ? "bg-indigo-600 text-white"
        : "bg-gray-50 text-gray-500 hover:bg-gray-100"
    }`}
  >
    ⚙️ Customize
  </button>
</div>
```

- [ ] **Step 6: Wrap existing modal content in Full QA conditional**

Wrap the existing Full QA toggle + page selector + testing mode + info banner in a conditional:
```tsx
{modalTab === "full" && (
  <>
    {/* Full QA toggle */}
    <label ...>...</label>

    {/* Per-page selection */}
    <div>...</div>

    {/* Testing mode */}
    <div>...</div>

    {/* Info */}
    <div className="bg-blue-50 ...">...</div>
  </>
)}
```

- [ ] **Step 7: Add Customize tab content**

After the Full QA conditional block, before the Actions block, add:
```tsx
{modalTab === "customize" && (
  <>
    {/* Page selector — same as Full QA but without the Full QA radio */}
    <div>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Select pages
      </p>
      <div className="space-y-2">
        {pages.map((page, idx) => (
          <div
            key={idx}
            className={`rounded-lg border transition-colors ${
              page.enabled ? "border-indigo-400 bg-indigo-50/50" : "border-gray-200"
            }`}
          >
            <label
              className="flex items-center gap-3 cursor-pointer px-3 py-2.5"
              onClick={(e) => {
                e.preventDefault();
                setPages((prev) =>
                  prev.map((p, i) =>
                    i === idx ? { ...p, enabled: !p.enabled } : p
                  )
                );
              }}
            >
              <input
                type="checkbox"
                checked={page.enabled}
                readOnly
                className="w-4 h-4 accent-indigo-600 rounded"
              />
              <span className="text-sm font-medium text-gray-700">{page.label}</span>
            </label>
          </div>
        ))}
      </div>
    </div>

    {/* Test type checkboxes */}
    <div>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Select tests to run
      </p>
      <div className="space-y-2">
        {TEST_TYPES.map((t) => (
          <label
            key={t.key}
            className={`flex items-start gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
              selectedTests.has(t.key)
                ? "border-indigo-400 bg-indigo-50/50"
                : "border-gray-200 hover:bg-gray-50"
            }`}
            onClick={(e) => {
              e.preventDefault();
              toggleTestType(t.key);
            }}
          >
            <input
              type="checkbox"
              checked={selectedTests.has(t.key)}
              readOnly
              className="w-4 h-4 accent-indigo-600 rounded mt-0.5"
            />
            <div>
              <div className="text-sm font-medium text-gray-800">
                {t.icon} {t.label}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">{t.desc}</div>
            </div>
          </label>
        ))}
      </div>
    </div>

    {/* Testing mode — identical to Full QA tab */}
    <div>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Testing mode</p>
      <div className="space-y-2">
        {TEST_MODES.map((mode) => (
          <label
            key={mode.value}
            className={`flex items-start gap-3 cursor-pointer px-3 py-2.5 rounded-lg border transition-colors ${
              testMode === mode.value
                ? "border-indigo-500 bg-indigo-50"
                : "border-gray-200 hover:bg-gray-50"
            }`}
          >
            <input
              type="radio"
              name="testModeCustomize"
              value={mode.value}
              checked={testMode === mode.value}
              onChange={() => setTestMode(mode.value as "design" | "ai")}
              className="w-4 h-4 accent-indigo-600 mt-0.5"
            />
            <div>
              <div className="text-sm font-medium text-gray-800">{mode.icon} {mode.label}</div>
              <div className="text-xs text-gray-500 mt-0.5">{mode.desc}</div>
            </div>
          </label>
        ))}
      </div>
    </div>
  </>
)}
```

- [ ] **Step 8: Update the action button**

Change the start button to be dynamic based on `modalTab` and disable when 0 tests selected in Customize tab:
```tsx
<button
  onClick={handleConfirm}
  disabled={
    isLoading ||
    !anyEnabled ||
    (modalTab === "customize" && selectedTests.size === 0)
  }
  className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
>
  {isLoading
    ? "Starting..."
    : modalTab === "customize"
    ? "⚙️ Run Selected Tests"
    : "🚀 Start QA Run"}
</button>
```

- [ ] **Step 9: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/runs/RunQAModal.tsx
git commit -m "feat: add Full QA / Customize tab bar to RunQAModal with test type checkboxes"
```

---

## Task 3: Add testTypes param to frontend API

**Files:**
- Modify: `frontend/src/api/runs.ts`

- [ ] **Step 1: Add testTypes to startRun**

Replace the existing `startRun` function:
```ts
export const startRun = (
  projectId: number,
  pages?: string,
  testMode: "design" | "ai" = "design",
  testTypes?: string[]
) => {
  const params = new URLSearchParams();
  if (pages) params.set("pages", pages);
  if (testMode !== "design") params.set("test_mode", testMode);
  if (testTypes && testTypes.length > 0) {
    testTypes.forEach((t) => params.append("test_types", t));
  }
  const qs = params.toString() ? `?${params.toString()}` : "";
  return api.post(`/api/projects/${projectId}/runs${qs}`);
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/runs.ts
git commit -m "feat: add test_types query param to startRun API call"
```

---

## Task 4: Accept test_types in backend router

**Files:**
- Modify: `backend/app/routers/runs.py`

- [ ] **Step 1: Update _dispatch_qa_task to accept test_types**

Change the function signature and `run_qa_job.delay` call:
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

- [ ] **Step 2: Add test_types query param to start_run endpoint**

In the `start_run` function signature, add after `test_mode`:
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

- [ ] **Step 3: Pass test_types to _dispatch_qa_task**

Change the dispatch call at the bottom of `start_run`:
```python
    partial_pages = [p.strip() for p in pages.split(",") if p.strip()] if pages else None
    _dispatch_qa_task(run.id, partial_pages, test_mode, test_types)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/runs.py
git commit -m "feat: accept test_types query param in start_run endpoint"
```

---

## Task 5: Apply test_types phase skipping in qa_tasks

**Files:**
- Modify: `backend/app/workers/qa_tasks.py`

- [ ] **Step 1: Add _should_run helper after PHASE_WEIGHTS**

Add right after the `PHASE_WEIGHTS` dict (after line 48):
```python
def _should_run(phase: str, test_types: Optional[list[str]]) -> bool:
    """Return True if this phase should run. None means run all."""
    if test_types is None:
        return True
    return phase in test_types
```

- [ ] **Step 2: Update run_qa_job Celery task signature**

Change `run_qa_job` (around line 708):
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

- [ ] **Step 3: Update _run_qa_job_async signature**

Change `_run_qa_job_async` (around line 164):
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

- [ ] **Step 4: Skip compare phase if "qa" not in test_types**

Find Phase 3 (compare phase) — look for `done_phases.append("compare")` and the block before it. Wrap the compare logic in:
```python
# ---- Phase 3: Compare ----
if _should_run("qa", test_types):
    # ... existing compare phase code ...
    done_phases.append("compare")
    _publish_fn(run_id, "compare", ..., message="Comparison complete")
else:
    done_phases.append("compare")
    _publish_fn(run_id, "compare", progress=_overall_progress(done_phases, "", 0), message="QA test skipped")
```

- [ ] **Step 5: Skip functional phase if "functional" not in test_types**

Find Phase 4 (functional). Wrap the functional engine block:
```python
# ---- Phase 4: Functional Tests ----
done_phases.append("compare")
if _should_run("functional", test_types):
    _publish_fn(run_id, "functional", ...)
    # ... existing functional code ...
    done_phases.append("functional")
    _publish_fn(run_id, "functional", ..., message="Functional tests complete")
else:
    done_phases.append("functional")
    _publish_fn(run_id, "functional", progress=_overall_progress(done_phases, "", 0), message="Functional test skipped")
```

- [ ] **Step 6: Skip ADA, SEO, Performance conditionally in the concurrent gather**

Replace the `asyncio.gather` call and save blocks with conditional logic.

Add two helper coroutines right before the page loop:
```python
async def _empty_list():
    return []

async def _empty_none():
    return None
```

Replace the gather inside the page loop:
```python
run_ada = _should_run("ada", test_types)
run_seo_or_perf = _should_run("seo", test_types) or _should_run("performance", test_types)

acc_results, link_items, seo_result = await asyncio.gather(
    accessibility_engine.run_checks(page_url=page_url, password=project.shopify_password)
    if run_ada else _empty_list(),
    link_engine.audit_page(page_url=page_url, password=project.shopify_password),
    seo_engine.analyze_page(page_url=page_url, password=project.shopify_password)
    if run_seo_or_perf else _empty_none(),
    return_exceptions=True,
)
```

Then update the save blocks — wrap acc save:
```python
if run_ada and not isinstance(acc_results, Exception):
    try:
        for ar in acc_results:
            db.add(AccessibilityResult(...))
        db.commit()
    except Exception:
        pass
```

Wrap SEO/performance save:
```python
if run_seo_or_perf:
    if isinstance(seo_result, Exception):
        logger.warning("SEO engine failed for %s: %s", page_name, seo_result)
    else:
        try:
            if _should_run("seo", test_types):
                for check in seo_result.seo_checks:
                    db.add(SeoResultModel(...))
            if _should_run("performance", test_types):
                perf = seo_result.performance
                db.add(PerformanceResult(...))
            db.commit()
        except Exception as e:
            logger.error("Failed to save SEO/performance results for %s: %s", page_name, e)
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/workers/qa_tasks.py
git commit -m "feat: add test_types phase skipping to qa_tasks pipeline"
```

---

## Task 6: End-to-end smoke test

- [ ] **Step 1: Start the dev server**

```bash
cd frontend && npm run dev
```
Expected: Vite starts, no compile errors

- [ ] **Step 2: Manual test — Full QA tab**

1. Open a project detail page
2. Confirm "Test Cases" tab is gone — only "Runs" and "Settings"
3. Click "Run QA" button
4. Modal opens showing "⚡ Full QA | ⚙️ Customize" tab bar
5. Full QA tab is active by default
6. Button text is "🚀 Start QA Run"

- [ ] **Step 3: Manual test — Customize tab**

1. Click "⚙️ Customize" tab
2. All 5 test checkboxes appear, all checked
3. Button text is "⚙️ Run Selected Tests"
4. Uncheck all boxes → button becomes disabled
5. Check at least one → button re-enables
6. Both "AI Analysis Only" and "Design Comparison" testing modes are visible

- [ ] **Step 4: Verify API call sends test_types**

Open browser DevTools → Network tab, start a Customize run with only SEO and Performance checked.
Expected: POST URL contains `test_types=seo&test_types=performance`

- [ ] **Step 5: Commit**

No code changes — this is a verification step. If issues found, fix them before committing.
