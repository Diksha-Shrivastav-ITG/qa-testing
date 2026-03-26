import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getRun, getCaptures, getAccessibility, getLinkAudit } from "../../api/runs";
import { listIssues } from "../../api/issues";
import { getProject } from "../../api/projects";

// ---------- Types ----------

interface Issue {
  id: number;
  type: string;
  severity: string;
  page?: string;
  breakpoint?: number;
  description: string;
  ai_suggestion?: string;
  element_selector?: string;
  screenshot_path?: string;
}

interface PaginatedResponse {
  items: Issue[];
  total: number;
  page: number;
  pages: number;
}

interface Capture {
  id: number;
  page: string;
  breakpoint: number;
  source: "shopify" | "design";
  image_url: string | null;
}

interface AccessibilityItem {
  id: number;
  page: string;
  test_name: string;
  severity: string;
  description: string;
  wcag?: string;
  element?: string;
  help_text?: string;
}

interface LinkAuditItem {
  id: number;
  page: string;
  element_type: string;
  text: string;
  href?: string;
  destination?: string;
  is_external: boolean;
  has_href: boolean;
  issue?: string;
  aria_label?: string;
}

interface RunData {
  id: number;
  project_id: number;
  status: string;
  overall_score?: number;
  run_number?: number;
  started_at: string;
  test_mode?: string;
}

// ---------- Helpers ----------

const BACKEND = "http://localhost:8000";

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  major: "bg-orange-100 text-orange-700",
  minor: "bg-yellow-100 text-yellow-600",
  error: "bg-red-100 text-red-700",
  warning: "bg-orange-100 text-orange-700",
  notice: "bg-blue-100 text-blue-600",
};

const sevStyle = (s: string) =>
  SEVERITY_STYLES[s?.toLowerCase()] ?? "bg-gray-100 text-gray-600";

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  error: 0,
  major: 1,
  warning: 1,
  minor: 2,
  notice: 3,
};

const sevOrder = (s: string) => SEVERITY_ORDER[s?.toLowerCase()] ?? 9;

const pageLabel = (p: string) => {
  if (!p || p === "home" || p === "/") return "Homepage";
  return p
    .replace(/^\//, "")
    .replace(/\//g, " > ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

const captureUrl = (imageUrl: string | null) => {
  if (!imageUrl) return undefined;
  return `${BACKEND}${imageUrl}`;
};

function groupBy<T>(arr: T[], key: (item: T) => string): Record<string, T[]> {
  const result: Record<string, T[]> = {};
  arr.forEach((item) => {
    const k = key(item);
    (result[k] ??= []).push(item);
  });
  return result;
}

const TYPE_LABELS: Record<string, { label: string; icon: string }> = {
  visual: { label: "Visual Design", icon: "paintbrush" },
  functional: { label: "Functional", icon: "gear" },
  content: { label: "Content", icon: "document" },
};

const typeLabel = (t: string) => TYPE_LABELS[t]?.label ?? t;

// ---------- Fetch all issues across pages ----------

async function fetchAllIssues(runId: number): Promise<Issue[]> {
  const firstPage = await listIssues(runId, { per_page: 100, page: 1 }).then(
    (r) => r.data as PaginatedResponse
  );

  const allItems: Issue[] = [...firstPage.items];
  const totalPages = firstPage.pages;

  if (totalPages > 1) {
    const remaining = Array.from({ length: totalPages - 1 }, (_, i) => i + 2);
    const results = await Promise.all(
      remaining.map((p) =>
        listIssues(runId, { per_page: 100, page: p }).then(
          (r) => (r.data as PaginatedResponse).items
        )
      )
    );
    results.forEach((items) => allItems.push(...items));
  }

  return allItems;
}

// ---------- Collapsible wrapper ----------

interface CollapsibleProps {
  defaultOpen?: boolean;
  header: (open: boolean, toggle: () => void) => React.ReactNode;
  children: React.ReactNode;
}

const Collapsible = ({ defaultOpen = true, header, children }: CollapsibleProps) => {
  const [open, setOpen] = useState(defaultOpen);
  const toggle = useCallback(() => setOpen((v) => !v), []);
  return (
    <div>
      {header(open, toggle)}
      {open && children}
    </div>
  );
};

// ---------- Issue Card ----------

interface IssueCardProps {
  issue: Issue;
  num: string;
}

const IssueCard = ({ issue, num }: IssueCardProps) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="p-3 bg-gray-50 rounded border border-gray-100 cursor-pointer hover:bg-gray-100 transition-colors"
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="flex items-start gap-3">
        <span className="text-xs font-mono text-gray-400 mt-0.5 shrink-0">
          {num}
        </span>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${sevStyle(
            issue.severity
          )}`}
        >
          {issue.severity}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm text-gray-800">{issue.description}</p>
          {issue.element_selector && (
            <p className="text-xs text-gray-400 mt-0.5 truncate">
              {issue.element_selector}
            </p>
          )}
          <div className="flex gap-3 mt-1">
            <span className="text-xs text-gray-400 capitalize">{issue.type}</span>
            {issue.breakpoint && (
              <span className="text-xs text-gray-400">
                {issue.breakpoint}px
              </span>
            )}
          </div>

          {expanded && issue.ai_suggestion && (
            <div className="mt-3">
              <div className="text-xs bg-blue-50 text-blue-700 px-3 py-2 rounded">
                <strong>AI Suggestion:</strong> {issue.ai_suggestion}
              </div>
            </div>
          )}
        </div>
        <span className="text-xs text-gray-300">{expanded ? "▲" : "▼"}</span>
      </div>
    </div>
  );
};

// ---------- Type Sub-section within a page ----------

interface TypeSubsectionProps {
  typeName: string;
  issues: Issue[];
  numberPrefix: string;
  startIdx: number;
}

const TypeSubsection = ({
  typeName,
  issues,
  numberPrefix,
  startIdx,
}: TypeSubsectionProps) => {
  return (
    <Collapsible
      defaultOpen={true}
      header={(open, toggle) => (
        <button
          onClick={toggle}
          className="w-full flex items-center justify-between px-3 py-2 hover:bg-gray-50 transition-colors text-left rounded"
        >
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
              {typeLabel(typeName)}
            </span>
            <span className="text-xs text-gray-400">
              ({issues.length} issue{issues.length !== 1 ? "s" : ""})
            </span>
          </div>
          <span className="text-gray-300 text-xs">{open ? "▲" : "▼"}</span>
        </button>
      )}
    >
      <div className="space-y-2 px-1 pb-2">
        {issues.map((issue, idx) => (
          <IssueCard
            key={issue.id}
            issue={issue}
            num={`${numberPrefix}.${startIdx + idx + 1}`}
          />
        ))}
      </div>
    </Collapsible>
  );
};

// ---------- Page Section ----------

interface PageSectionProps {
  pageName: string;
  pageNumber: number;
  issues: Issue[];
  captures: Capture[];
}

const PageSection = ({
  pageName,
  pageNumber,
  issues,
  captures,
}: PageSectionProps) => {
  // Find the shopify full-page screenshot for the largest breakpoint
  const pageCaptures = captures.filter(
    (c) => c.page === pageName && c.source === "shopify"
  );
  const bestCapture =
    pageCaptures.sort((a, b) => b.breakpoint - a.breakpoint)[0] ?? null;

  // Group issues by type, with a stable ordering
  const typeOrder = ["visual", "functional", "content"];
  const byType = groupBy(issues, (i) => i.type ?? "other");
  const orderedTypes = typeOrder.filter((t) => byType[t]?.length);
  // Add any remaining types not in the standard list
  Object.keys(byType).forEach((t) => {
    if (!orderedTypes.includes(t)) orderedTypes.push(t);
  });

  // Sort issues within each type by severity
  orderedTypes.forEach((t) => {
    byType[t].sort((a, b) => sevOrder(a.severity) - sevOrder(b.severity));
  });

  // Compute sequential numbering offset for each type group
  let runningIdx = 0;
  const typeOffsets: Record<string, number> = {};
  orderedTypes.forEach((t) => {
    typeOffsets[t] = runningIdx;
    runningIdx += byType[t].length;
  });

  const critCount = issues.filter((i) => i.severity === "critical").length;
  const majorCount = issues.filter((i) => i.severity === "major").length;

  return (
    <Collapsible
      defaultOpen={true}
      header={(open, toggle) => (
        <button
          onClick={toggle}
          className="w-full flex items-center justify-between px-5 py-4 bg-gray-50 hover:bg-gray-100 transition-colors text-left border-b border-gray-200"
        >
          <div className="flex items-center gap-3">
            <span className="bg-blue-600 text-white text-xs font-bold rounded-full w-7 h-7 flex items-center justify-center">
              {pageNumber}
            </span>
            <span className="font-semibold text-gray-900 text-base">
              {pageLabel(pageName)}
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                issues.length > 0
                  ? "bg-red-100 text-red-700"
                  : "bg-green-100 text-green-700"
              }`}
            >
              {issues.length} issue{issues.length !== 1 ? "s" : ""}
            </span>
            {critCount > 0 && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-red-600 text-white font-medium">
                {critCount} critical
              </span>
            )}
            {majorCount > 0 && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-orange-500 text-white font-medium">
                {majorCount} major
              </span>
            )}
          </div>
          <span className="text-gray-400">{open ? "▲" : "▼"}</span>
        </button>
      )}
    >
      <div className="flex gap-6 p-5">
        {/* Left: full-page screenshot */}
        <div className="w-[340px] shrink-0">
          <div className="sticky top-4">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Full Page Screenshot
            </div>
            <div className="border border-gray-200 rounded-lg overflow-hidden bg-gray-50">
              {bestCapture?.image_url ? (
                <img
                  src={captureUrl(bestCapture.image_url)}
                  alt={`${pageLabel(pageName)} screenshot`}
                  className="w-full object-contain"
                  style={{ maxHeight: "800px" }}
                />
              ) : (
                <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
                  No screenshot available
                </div>
              )}
            </div>
            {bestCapture && (
              <div className="text-xs text-gray-400 mt-1 text-center">
                {bestCapture.breakpoint}px breakpoint
              </div>
            )}
          </div>
        </div>

        {/* Right: issues list grouped by type */}
        <div className="flex-1 min-w-0 space-y-3">
          {issues.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <div className="text-2xl mb-2">No issues found for this page</div>
            </div>
          ) : (
            orderedTypes.map((typeName) => (
              <TypeSubsection
                key={typeName}
                typeName={typeName}
                issues={byType[typeName]}
                numberPrefix={`${pageNumber}`}
                startIdx={typeOffsets[typeName]}
              />
            ))
          )}
        </div>
      </div>
    </Collapsible>
  );
};

// ---------- Accessibility Section ----------

interface AccSectionProps {
  items: AccessibilityItem[];
  sectionNum: number;
}

const AccessibilitySection = ({ items, sectionNum }: AccSectionProps) => {
  const byPage = groupBy(items, (i) => i.page);
  let sub = 0;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <Collapsible
        defaultOpen={true}
        header={(open, toggle) => (
          <button
            onClick={toggle}
            className="w-full flex items-center justify-between px-5 py-3.5 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              <span className="text-lg">&#9855;</span>
              <span className="font-semibold text-gray-900">
                {sectionNum}. ADA / Accessibility Issues
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  items.length > 0
                    ? "bg-red-100 text-red-700"
                    : "bg-green-100 text-green-700"
                }`}
              >
                {items.length} issue{items.length !== 1 ? "s" : ""}
              </span>
            </div>
            <span className="text-gray-400">{open ? "▲" : "▼"}</span>
          </button>
        )}
      >
        <div className="p-4 space-y-4">
          {Object.entries(byPage).map(([page, pageItems]) => {
            sub++;
            return (
              <div
                key={page}
                className="border border-gray-100 rounded-lg p-3 space-y-2"
              >
                <h4 className="text-sm font-medium text-gray-700">
                  {sectionNum}.{sub} {pageLabel(page)}
                </h4>
                {pageItems.map((item, idx) => (
                  <div
                    key={item.id}
                    className="p-2 bg-gray-50 rounded border border-gray-100 text-sm"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-xs font-mono text-gray-400">
                        {sectionNum}.{sub}.{idx + 1}
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${sevStyle(
                          item.severity
                        )}`}
                      >
                        {item.severity}
                      </span>
                      <div className="min-w-0">
                        <p className="text-gray-800">{item.description}</p>
                        {item.wcag && (
                          <p className="text-xs text-blue-500 mt-0.5">
                            WCAG: {item.wcag}
                          </p>
                        )}
                        {item.element && (
                          <p className="text-xs text-gray-400 font-mono mt-0.5 truncate">
                            {item.element}
                          </p>
                        )}
                        {item.help_text && (
                          <p className="text-xs text-gray-500 mt-1">
                            {item.help_text}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
          {items.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">
              No accessibility issues found
            </p>
          )}
        </div>
      </Collapsible>
    </div>
  );
};

// ---------- Link Audit Section ----------

interface LinkSectionProps {
  items: LinkAuditItem[];
  sectionNum: number;
}

const LinkAuditSection = ({ items, sectionNum }: LinkSectionProps) => {
  const issueItems = items.filter((i) => i.issue);
  const byPage = groupBy(items, (i) => i.page);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <Collapsible
        defaultOpen={false}
        header={(open, toggle) => (
          <button
            onClick={toggle}
            className="w-full flex items-center justify-between px-5 py-3.5 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              <span className="text-lg">&#128279;</span>
              <span className="font-semibold text-gray-900">
                {sectionNum}. Link & Button Audit
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  issueItems.length > 0
                    ? "bg-red-100 text-red-700"
                    : "bg-green-100 text-green-700"
                }`}
              >
                {issueItems.length} issue{issueItems.length !== 1 ? "s" : ""}
              </span>
            </div>
            <span className="text-gray-400">{open ? "▲" : "▼"}</span>
          </button>
        )}
      >
        <div className="p-4 space-y-4">
          {Object.entries(byPage).map(([page, pageItems]) => (
            <div
              key={page}
              className="border border-gray-100 rounded-lg p-3 space-y-1"
            >
              <h4 className="text-sm font-medium text-gray-700 mb-2">
                {pageLabel(page)}
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="py-1 pr-3">Type</th>
                      <th className="py-1 pr-3">Text</th>
                      <th className="py-1 pr-3">Destination</th>
                      <th className="py-1 pr-3">Has href</th>
                      <th className="py-1">Issue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((item) => (
                      <tr
                        key={item.id}
                        className={`border-b border-gray-50 ${
                          item.issue ? "bg-red-50" : ""
                        }`}
                      >
                        <td className="py-1 pr-3 font-mono">
                          {item.element_type}
                        </td>
                        <td className="py-1 pr-3 max-w-[150px] truncate">
                          {item.text || "\u2014"}
                        </td>
                        <td className="py-1 pr-3 max-w-[200px] truncate text-blue-500">
                          {item.destination || item.href || "\u2014"}
                        </td>
                        <td className="py-1 pr-3">
                          {item.has_href ? "\u2713" : "\u2717"}
                        </td>
                        <td className="py-1 text-red-600">
                          {item.issue || "\u2014"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          {items.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">
              No links audited
            </p>
          )}
        </div>
      </Collapsible>
    </div>
  );
};

// ---------- Score Card ----------

interface ScoreCardProps {
  score: number | null;
  threshold: number;
  issues: Issue[];
  accCount: number;
  testMode?: string;
}

const ScoreCard = ({ score, threshold, issues, accCount, testMode }: ScoreCardProps) => {
  const passed = score !== null && score >= threshold;
  const critCount = issues.filter((i) => i.severity === "critical").length;
  const majorCount = issues.filter((i) => i.severity === "major").length;
  const minorCount = issues.filter(
    (i) => i.severity !== "critical" && i.severity !== "major"
  ).length;

  // Progress bar width
  const barWidth = score !== null ? Math.min(score, 100) : 0;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <div className="flex items-center gap-6">
        {/* Score circle */}
        <div className="text-center min-w-[100px]">
          <div
            className={`text-5xl font-bold ${
              score === null
                ? "text-gray-400"
                : passed
                ? "text-green-600"
                : "text-red-600"
            }`}
          >
            {score !== null ? score : "\u2014"}
          </div>
          <div className="text-xs text-gray-500 mt-1">/ 100</div>
        </div>

        {/* Details */}
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h2 className="text-lg font-semibold text-gray-900">QA Results</h2>
            {score !== null && (
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                  passed
                    ? "bg-green-100 text-green-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {passed ? "QA Passed" : "QA Failed"}
              </span>
            )}
            {testMode === "ai" && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">
                AI Mode
              </span>
            )}
          </div>

          {/* Progress bar */}
          {score !== null && (
            <div className="w-full bg-gray-200 rounded-full h-2 mb-3">
              <div
                className={`h-2 rounded-full transition-all ${
                  passed ? "bg-green-500" : "bg-red-500"
                }`}
                style={{ width: `${barWidth}%` }}
              />
            </div>
          )}

          <div className="flex flex-wrap gap-4 text-sm text-gray-500">
            <span>
              Threshold:{" "}
              <strong className="text-gray-700">{threshold}%</strong>
            </span>
            <span>
              Total Issues:{" "}
              <strong className="text-gray-700">{issues.length}</strong>
            </span>
            <span className="text-red-600">
              Critical: <strong>{critCount}</strong>
            </span>
            <span className="text-orange-600">
              Major: <strong>{majorCount}</strong>
            </span>
            <span className="text-yellow-600">
              Minor: <strong>{minorCount}</strong>
            </span>
            <span>
              ADA Issues:{" "}
              <strong className="text-gray-700">{accCount}</strong>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

// ---------- Main Component ----------

interface RunResultsProps {
  runId: number;
}

const RunResults = ({ runId }: RunResultsProps) => {
  // ---------- Data fetching ----------

  const {
    data: run,
    isLoading: runLoading,
    isError: runError,
  } = useQuery<RunData>({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId).then((r) => r.data),
    enabled: !!runId,
  });

  // Fetch ALL issues across all pages
  const { data: allIssues, isLoading: issuesLoading } = useQuery<Issue[]>({
    queryKey: ["allIssues", runId],
    queryFn: () => fetchAllIssues(runId),
    enabled: !!runId,
  });

  const { data: capturesData } = useQuery<Capture[]>({
    queryKey: ["captures", runId],
    queryFn: () => getCaptures(runId).then((r) => r.data),
    enabled: !!runId,
  });

  const { data: accData } = useQuery<AccessibilityItem[]>({
    queryKey: ["accessibility", runId],
    queryFn: () => getAccessibility(runId).then((r) => r.data),
    enabled: !!runId,
  });

  const { data: linkData } = useQuery<LinkAuditItem[]>({
    queryKey: ["linkAudit", runId],
    queryFn: () => getLinkAudit(runId).then((r) => r.data),
    enabled: !!runId,
  });

  // Fetch project for threshold
  const { data: projectData } = useQuery({
    queryKey: ["project", run?.project_id],
    queryFn: () => getProject(run!.project_id).then((r) => r.data),
    enabled: !!run?.project_id,
  });

  // ---------- Loading / Error states ----------

  if (runLoading || issuesLoading) {
    return (
      <div className="text-gray-500 text-sm py-8 text-center">
        Loading results...
      </div>
    );
  }
  if (runError || !run) {
    return (
      <div className="text-red-500 text-sm py-8 text-center">
        Failed to load run results.
      </div>
    );
  }

  // ---------- Derived data ----------

  const score =
    run.overall_score != null ? Math.round(run.overall_score) : null;
  const threshold = projectData?.pass_threshold ?? 90;
  const issues: Issue[] = allIssues ?? [];
  const captures: Capture[] = capturesData ?? [];
  const accItems: AccessibilityItem[] = accData ?? [];
  const linkItems: LinkAuditItem[] = linkData ?? [];

  // Group issues by page
  const issuesByPage = groupBy(issues, (i) => i.page ?? "home");

  // Determine unique pages (from both issues and captures) and sort them
  const allPages = new Set<string>();
  issues.forEach((i) => allPages.add(i.page ?? "home"));
  // Also include pages from captures that might not have issues
  captures.forEach((c) => allPages.add(c.page));

  const pageList = Array.from(allPages).sort((a, b) => {
    // Homepage first
    if (a === "home" || a === "/") return -1;
    if (b === "home" || b === "/") return 1;
    return a.localeCompare(b);
  });

  // Only show pages that have issues
  const pagesWithIssues = pageList.filter(
    (p) => issuesByPage[p]?.length > 0
  );

  // Section numbering: pages first, then accessibility, then link audit
  const accSectionNum = pagesWithIssues.length + 1;
  const linkSectionNum = pagesWithIssues.length + 2;

  return (
    <div className="space-y-6">
      {/* Score Card */}
      <ScoreCard
        score={score}
        threshold={threshold}
        issues={issues}
        accCount={accItems.length}
        testMode={run.test_mode}
      />

      {/* Summary bar */}
      <div className="bg-white border border-gray-200 rounded-lg px-5 py-3 flex items-center justify-between text-sm">
        <div className="flex items-center gap-4">
          <span className="text-gray-500">
            Pages analyzed:{" "}
            <strong className="text-gray-800">{pageList.length}</strong>
          </span>
          <span className="text-gray-300">|</span>
          <span className="text-gray-500">
            Total issues:{" "}
            <strong className="text-gray-800">{issues.length}</strong>
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          Showing all {issues.length} issues across {pagesWithIssues.length}{" "}
          page{pagesWithIssues.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Page-by-page sections */}
      {pagesWithIssues.map((pageName, idx) => (
        <div
          key={pageName}
          className="border border-gray-200 rounded-lg overflow-hidden"
        >
          <PageSection
            pageName={pageName}
            pageNumber={idx + 1}
            issues={issuesByPage[pageName] ?? []}
            captures={captures}
          />
        </div>
      ))}

      {/* Accessibility Section */}
      <AccessibilitySection items={accItems} sectionNum={accSectionNum} />

      {/* Link Audit Section */}
      <LinkAuditSection items={linkItems} sectionNum={linkSectionNum} />

      {/* No issues at all */}
      {issues.length === 0 && accItems.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <div className="text-4xl mb-3">&#10003;</div>
          <p className="text-lg font-medium">No issues found</p>
          <p className="text-sm mt-1">Your site looks great!</p>
        </div>
      )}
    </div>
  );
};

export default RunResults;
