# Website Source Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `website` source type so users can manually map Shopify pages to full URLs on any custom/static website (e.g., Netlify) for visual comparison testing.

**Architecture:** Add `website` to the `SourceType` enum. When selected, the user provides explicit `{shopify_path: design_url}` mappings stored in `project.config["page_mappings"]`. The QA pipeline already skips discovery when `page_mappings` exist, so the main backend change is in the capture phase where design URLs must be used as-is (full URLs) instead of base+path. The frontend gets a repeatable row form for entering mappings.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic (backend), React/TypeScript/TailwindCSS (frontend), PostgreSQL

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/models/project.py` | Add `website` to `SourceType` enum |
| Create | `backend/alembic/versions/f6a7b8c9d0e1_add_website_source_type.py` | DB migration for new enum value |
| Modify | `backend/app/schemas/project.py` | Add `page_mappings` field to create/update schemas |
| Modify | `backend/app/routers/projects.py` | Store `page_mappings` on create/update; handle `website` in discover endpoint |
| Modify | `backend/app/workers/qa_tasks.py` | Update `has_design_source` check; use full URL for website type in capture phase |
| Modify | `backend/tests/test_projects.py` | Test creating/updating website projects with page_mappings |
| Modify | `frontend/src/api/projects.ts` | Add `page_mappings` to create project payload type |
| Modify | `frontend/src/components/projects/ProjectForm.tsx` | Add Website option + repeatable row form for mappings |
| Modify | `frontend/src/components/projects/ProjectCard.tsx` | Show "Website" badge |
| Modify | `frontend/src/pages/ProjectDetailPage.tsx` | Show "Website" label and mappings in settings |

---

### Task 1: Add `website` to SourceType Enum + Migration

**Files:**
- Modify: `backend/app/models/project.py:16-19`
- Create: `backend/alembic/versions/f6a7b8c9d0e1_add_website_source_type.py`

- [ ] **Step 1: Add `website` to the SourceType enum**

In `backend/app/models/project.py`, add `website` to the enum class:

```python
class SourceType(str, enum.Enum):
    framer = "framer"
    figma = "figma"
    website = "website"
    none = "none"
```

- [ ] **Step 2: Create the Alembic migration**

Create file `backend/alembic/versions/f6a7b8c9d0e1_add_website_source_type.py`:

```python
"""add website to sourcetype enum

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-31 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'website'"))


def downgrade() -> None:
    pass
```

- [ ] **Step 3: Run the migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies without errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/project.py backend/alembic/versions/f6a7b8c9d0e1_add_website_source_type.py
git commit -m "feat: add website to SourceType enum with migration"
```

---

### Task 2: Add `page_mappings` to Schemas + API

**Files:**
- Modify: `backend/app/schemas/project.py:11-19`
- Modify: `backend/app/routers/projects.py:29-50,85-103`
- Test: `backend/tests/test_projects.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_projects.py`:

```python
def test_create_website_project_with_mappings(client: TestClient, developer_token: str):
    """Create a website project with page_mappings stored in config."""
    payload = {
        "name": "Website QA",
        "shopify_url": "https://store.myshopify.com",
        "source_type": "website",
        "page_mappings": {
            "/": "https://design.netlify.app/index.html",
            "/collections": "https://design.netlify.app/collection.html",
        },
    }
    resp = client.post("/api/projects", json=payload, headers=auth_header(developer_token))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source_type"] == "website"
    assert body["source_url"] is None

    # Verify mappings stored — fetch project and check via mappings endpoint
    project_id = body["id"]
    mappings_resp = client.get(
        f"/api/projects/{project_id}/mappings",
        headers=auth_header(developer_token),
    )
    assert mappings_resp.status_code == 200, mappings_resp.text
    mappings = mappings_resp.json()
    assert mappings["/"] == "https://design.netlify.app/index.html"
    assert mappings["/collections"] == "https://design.netlify.app/collection.html"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_projects.py::test_create_website_project_with_mappings -v`
Expected: FAIL — `page_mappings` field not recognized by `ProjectCreate`.

- [ ] **Step 3: Add `page_mappings` to schemas**

In `backend/app/schemas/project.py`, add the field to both `ProjectCreate` and `ProjectUpdate`:

```python
class ProjectCreate(BaseModel):
    name: str
    shopify_url: str
    source_type: SourceType = SourceType.none
    source_url: Optional[str] = None
    shopify_password: Optional[str] = None
    framer_password: Optional[str] = None
    figma_token: Optional[str] = None
    pass_threshold: float = 90.0
    page_mappings: Optional[dict[str, str]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    shopify_url: Optional[str] = None
    source_url: Optional[str] = None
    shopify_password: Optional[str] = None
    framer_password: Optional[str] = None
    figma_token: Optional[str] = None
    pass_threshold: Optional[float] = None
    page_mappings: Optional[dict[str, str]] = None
```

- [ ] **Step 4: Store `page_mappings` in config on create**

In `backend/app/routers/projects.py`, modify `create_project` (around line 35-49). Replace the existing function body:

```python
@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "developer")),
) -> ProjectResponse:
    config: dict = {}
    if payload.page_mappings:
        config["page_mappings"] = payload.page_mappings

    project = Project(
        name=payload.name,
        shopify_url=payload.shopify_url,
        source_type=payload.source_type,
        source_url=payload.source_url,
        shopify_password=payload.shopify_password,
        framer_password=payload.framer_password,
        figma_token=payload.figma_token,
        pass_threshold=payload.pass_threshold,
        created_by=current_user.id,
        config=config,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project  # type: ignore[return-value]
```

- [ ] **Step 5: Store `page_mappings` in config on update**

In `backend/app/routers/projects.py`, modify `update_project` (around line 85-103). After `for field, value in update_data.items():`, add handling for `page_mappings`:

```python
@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    check_project_owner(project, current_user)

    update_data = payload.model_dump(exclude_unset=True)

    # Handle page_mappings separately — stored in config, not a column
    page_mappings = update_data.pop("page_mappings", None)
    if page_mappings is not None:
        config = dict(project.config or {})
        config["page_mappings"] = page_mappings
        project.config = config

    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project  # type: ignore[return-value]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_projects.py::test_create_website_project_with_mappings -v`
Expected: PASS

- [ ] **Step 7: Run all project tests to check for regressions**

Run: `cd backend && python -m pytest tests/test_projects.py -v`
Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/project.py backend/app/routers/projects.py backend/tests/test_projects.py
git commit -m "feat: add page_mappings to project create/update for website source type"
```

---

### Task 3: Handle `website` in Discovery Endpoint

**Files:**
- Modify: `backend/app/routers/projects.py:137-187`

- [ ] **Step 1: Update discover_project to handle website type**

In `backend/app/routers/projects.py`, find the `discover_project` function (line 137). Add a branch for `website` before the `try` block. The full updated function:

```python
@router.post("/{project_id}/discover")
def discover_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "developer")),
) -> dict:
    """Discover pages for both Shopify and source sites, auto-map them,
    persist mappings in project.config, and return the result."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    check_project_owner(project, current_user)

    # Website type: mappings are manual — return stored mappings
    if project.source_type.value == "website":
        mappings = (project.config or {}).get("page_mappings", {})
        shopify_pages = [{"path": k, "name": k.strip("/") or "Homepage"} for k in mappings]
        return {
            "shopify_pages": shopify_pages,
            "source_pages": [],
            "mappings": mappings,
        }

    from app.engines.discovery_engine import DiscoveryEngine

    engine = DiscoveryEngine()

    async def _run_discovery() -> tuple[list[dict], list[dict]]:
        shopify_pages = await engine.discover_pages(
            project.shopify_url,
            password=project.shopify_password,
        )
        if project.source_type.value == "framer":
            source_pages = await engine.discover_framer_pages(project.source_url)
        else:
            # For figma or unknown source types, return empty list — no browser discovery
            source_pages = []
        return shopify_pages, source_pages

    try:
        shopify_pages, source_pages = asyncio.run(_run_discovery())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Discovery failed: {exc}",
        ) from exc

    mappings = engine.auto_map(shopify_pages, source_pages)

    # Persist mappings into project.config
    config: dict[str, Any] = dict(project.config or {})
    config["mappings"] = mappings
    project.config = config
    db.commit()
    db.refresh(project)

    return {
        "shopify_pages": shopify_pages,
        "source_pages": source_pages,
        "mappings": mappings,
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/projects.py
git commit -m "feat: handle website source type in discovery endpoint"
```

---

### Task 4: Update QA Task — `has_design_source` + Capture Phase

**Files:**
- Modify: `backend/app/workers/qa_tasks.py:234-238,336`

- [ ] **Step 1: Update `has_design_source` check**

In `backend/app/workers/qa_tasks.py`, find lines 234-238 and replace with:

```python
        has_design_source = (
            project.source_type == SourceType.website
            or (
                project.source_url
                and project.source_url.strip()
                and project.source_type != SourceType.none
            )
        )
```

- [ ] **Step 2: Update source URL construction in capture phase**

In `backend/app/workers/qa_tasks.py`, find line 336:

```python
                source_url = (project.source_url or "").rstrip("/") + source_path
```

Replace with:

```python
                if project.source_type == SourceType.website:
                    source_url = source_path  # full URL stored in mapping
                else:
                    source_url = (project.source_url or "").rstrip("/") + source_path
```

- [ ] **Step 3: Verify no password is passed for website captures**

In the same capture block (around line 346-353), the design capture currently passes `password=project.framer_password`. For website type there's no password. Update:

```python
                    capture_engine.capture_page(
                        url=source_url,
                        page_name=page_name,
                        run_dir=run_dir,
                        source="design",
                        breakpoints=BREAKPOINTS,
                        password=project.framer_password if project.source_type != SourceType.website else None,
                    ),
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/workers/qa_tasks.py
git commit -m "feat: support website source type in QA capture pipeline"
```

---

### Task 5: Frontend — API Client Update

**Files:**
- Modify: `frontend/src/api/projects.ts:8-15`

- [ ] **Step 1: Add `page_mappings` to the create project type**

In `frontend/src/api/projects.ts`, update the `createProject` function signature:

```typescript
export const createProject = (data: {
  name: string;
  shopify_url: string;
  source_type: string;
  source_url?: string;
  shopify_password?: string;
  figma_token?: string;
  page_mappings?: Record<string, string>;
}) => api.post("/api/projects", data);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/projects.ts
git commit -m "feat: add page_mappings to createProject API type"
```

---

### Task 6: Frontend — ProjectForm with Repeatable Row Mapping

**Files:**
- Modify: `frontend/src/components/projects/ProjectForm.tsx`

- [ ] **Step 1: Add page_mappings state and Website option**

Replace the entire `frontend/src/components/projects/ProjectForm.tsx` with:

```tsx
import { useState } from "react";

interface PageMapping {
  shopify_path: string;
  design_url: string;
}

interface ProjectFormData {
  name: string;
  shopify_url: string;
  source_type: string;
  source_url?: string;
  shopify_password?: string;
  figma_token?: string;
  page_mappings?: Record<string, string>;
}

interface ProjectFormProps {
  onSubmit: (data: ProjectFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const ProjectForm = ({ onSubmit, onCancel, isLoading }: ProjectFormProps) => {
  const [form, setForm] = useState<ProjectFormData>({
    name: "",
    shopify_url: "",
    source_type: "none",
    source_url: "",
    shopify_password: "",
    figma_token: "",
  });

  const [mappingRows, setMappingRows] = useState<PageMapping[]>([
    { shopify_path: "/", design_url: "" },
  ]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleMappingChange = (
    index: number,
    field: keyof PageMapping,
    value: string
  ) => {
    setMappingRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    );
  };

  const addMappingRow = () => {
    setMappingRows((prev) => [...prev, { shopify_path: "", design_url: "" }]);
  };

  const removeMappingRow = (index: number) => {
    setMappingRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const data: ProjectFormData = {
      name: form.name,
      shopify_url: form.shopify_url,
      source_type: form.source_type,
    };
    if (form.source_type === "website") {
      // Convert rows to { shopify_path: design_url } dict
      const mappings: Record<string, string> = {};
      for (const row of mappingRows) {
        if (row.shopify_path.trim() && row.design_url.trim()) {
          mappings[row.shopify_path.trim()] = row.design_url.trim();
        }
      }
      if (Object.keys(mappings).length > 0) {
        data.page_mappings = mappings;
      }
    } else {
      if (form.source_url) data.source_url = form.source_url;
    }
    if (form.shopify_password) data.shopify_password = form.shopify_password;
    if (form.figma_token) data.figma_token = form.figma_token;
    onSubmit(data);
  };

  const isWebsite = form.source_type === "website";
  const hasDesignSource = form.source_type !== "none" && !isWebsite;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">
          New Project
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Project Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              name="name"
              value={form.name}
              onChange={handleChange}
              required
              placeholder="My Shopify Store"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Shopify URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Shopify URL <span className="text-red-500">*</span>
            </label>
            <input
              type="url"
              name="shopify_url"
              value={form.shopify_url}
              onChange={handleChange}
              required
              placeholder="https://mystore.myshopify.com"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Source Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Design Source
            </label>
            <select
              name="source_type"
              value={form.source_type}
              onChange={handleChange}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="none">None (AI testing only)</option>
              <option value="framer">Framer</option>
              <option value="figma">Figma</option>
              <option value="website">Website</option>
            </select>
            {form.source_type === "none" && (
              <p className="mt-1 text-xs text-gray-400">
                No design reference — QA will use AI analysis to review your Shopify site
              </p>
            )}
            {isWebsite && (
              <p className="mt-1 text-xs text-gray-400">
                Custom website — provide individual page URLs below
              </p>
            )}
          </div>

          {/* Source URL — only shown when Framer/Figma selected */}
          {hasDesignSource && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {form.source_type === "figma" ? "Figma" : "Framer"} URL{" "}
                <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                name="source_url"
                value={form.source_url}
                onChange={handleChange}
                required
                placeholder="https://..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Page Mappings — only shown when Website selected */}
          {isWebsite && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Page Mappings <span className="text-red-500">*</span>
              </label>
              <div className="space-y-2">
                {mappingRows.map((row, index) => (
                  <div key={index} className="flex gap-2 items-start">
                    <input
                      type="text"
                      value={row.shopify_path}
                      onChange={(e) =>
                        handleMappingChange(index, "shopify_path", e.target.value)
                      }
                      placeholder="Shopify path, e.g. /"
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <input
                      type="url"
                      value={row.design_url}
                      onChange={(e) =>
                        handleMappingChange(index, "design_url", e.target.value)
                      }
                      placeholder="Design URL"
                      className="flex-[2] px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    {mappingRows.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeMappingRow(index)}
                        className="px-2 py-2 text-red-500 hover:text-red-700 text-sm"
                        title="Remove row"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={addMappingRow}
                className="mt-2 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
              >
                + Add Page
              </button>
            </div>
          )}

          {/* Optional: Shopify Password */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Shopify Password{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="password"
              name="shopify_password"
              value={form.shopify_password}
              onChange={handleChange}
              placeholder="Password-protected store access"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Optional: Figma Token */}
          {form.source_type === "figma" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Figma Token{" "}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <input
                type="password"
                name="figma_token"
                value={form.figma_token}
                onChange={handleChange}
                placeholder="figd_..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
            >
              {isLoading ? "Creating..." : "Create Project"}
            </button>
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-60 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ProjectForm;
```

- [ ] **Step 2: Verify the form renders**

Run: `cd frontend && npm run dev`
Open the browser, click "New Project", select "Website" from the dropdown. Verify:
- The single "Source URL" field is hidden
- A repeatable row form appears with Shopify path + Design URL fields
- "+ Add Page" adds rows
- X button removes rows (not shown when only 1 row)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/projects/ProjectForm.tsx
git commit -m "feat: add Website option with page mapping rows to ProjectForm"
```

---

### Task 7: Frontend — ProjectCard Badge

**Files:**
- Modify: `frontend/src/components/projects/ProjectCard.tsx:15-28`

- [ ] **Step 1: Add website badge to sourceTypeBadge function**

In `frontend/src/components/projects/ProjectCard.tsx`, replace the `sourceTypeBadge` function (lines 15-28):

```tsx
const sourceTypeBadge = (sourceType: string) => {
  if (sourceType === "figma") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
        Figma
      </span>
    );
  }
  if (sourceType === "website") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
        Website
      </span>
    );
  }
  if (sourceType === "none") {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
        AI Only
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
      Framer
    </span>
  );
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/projects/ProjectCard.tsx
git commit -m "feat: add Website badge to ProjectCard"
```

---

### Task 8: Frontend — ProjectDetailPage Settings

**Files:**
- Modify: `frontend/src/pages/ProjectDetailPage.tsx:258-279`

- [ ] **Step 1: Show "Website" label and mappings info in settings view**

In `frontend/src/pages/ProjectDetailPage.tsx`, find the settings display section (around line 258-279). Replace the Source URL block to handle website type. Replace the entire non-edit settings `<div>` (lines 258-292):

```tsx
            <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  Shopify URL
                </div>
                <div className="text-sm text-gray-900">{project.shopify_url}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  Source Type
                </div>
                <div className="text-sm text-gray-900 capitalize">
                  {project.source_type === "website" ? "Website" : project.source_type}
                </div>
              </div>
              {project.source_type !== "website" && (
                <div>
                  <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                    Source URL
                  </div>
                  <div className="text-sm text-gray-900 break-all">
                    {project.source_url}
                  </div>
                </div>
              )}
              <button
                onClick={() => {
                  setSettingsForm({
                    shopify_url: project.shopify_url,
                    source_url: project.source_url,
                  });
                  setEditMode(true);
                }}
                className="px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors"
              >
                Edit Settings
              </button>
            </div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ProjectDetailPage.tsx
git commit -m "feat: show Website source type in project settings"
```

---

### Task 9: Run All Backend Tests

**Files:** None (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS. No regressions from existing Framer/Figma/none projects.

- [ ] **Step 2: If any tests fail, fix them and commit**

If a test fails due to the new `page_mappings` field or updated functions, fix the issue and commit the fix.
