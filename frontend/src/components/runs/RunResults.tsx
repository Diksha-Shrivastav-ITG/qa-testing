import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { getRun, getCaptures, getComparisons, getAccessibility, getLinkAudit, getSeo, getPerformance } from "../../api/runs";
import SideBySideViewer from "../comparison/SideBySideViewer";
import { listIssues } from "../../api/issues";
import { getProject } from "../../api/projects";
import PromptBuilder from "./PromptBuilder";

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

interface PageConfigData {
  label: string;
  mode: string;
  shopify_url: string;
  reference_url?: string | null;
}

interface ComparisonItem {
  id: number;
  page: string;
  breakpoint: number;
  ssim_score: number | null;
  diff_image_url: string | null;
  heatmap_url: string | null;
  ai_analysis_status: string;
}

interface RunData {
  id: number;
  project_id: number;
  status: string;
  overall_score?: number;
  run_number?: number;
  started_at: string;
  test_mode?: string;
  test_types?: string | null; // comma-separated, null = Full QA (all tests)
  page_configs?: PageConfigData[] | null;
}

// ---------- Helpers ----------

const BACKEND = "";

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-red-500/10 text-red-400 border border-red-500/25",
  major:    "bg-orange-500/10 text-orange-400 border border-orange-500/25",
  minor:    "bg-yellow-500/10 text-yellow-400 border border-yellow-500/25",
  error:    "bg-red-500/10 text-red-400 border border-red-500/25",
  warning:  "bg-orange-500/10 text-orange-400 border border-orange-500/25",
  notice:   "bg-blue-500/10 text-blue-400 border border-blue-500/25",
};

const sevStyle = (s: string) =>
  SEVERITY_STYLES[s?.toLowerCase()] ?? "bg-gray-100 dark:bg-slate-700/60 text-gray-500 dark:text-slate-400 border border-gray-300 dark:border-slate-600";

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

const Collapsible = ({ defaultOpen = false, header, children }: CollapsibleProps) => {
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
      className="p-3 bg-gray-50 dark:bg-slate-700/30 rounded-xl border border-gray-200 dark:border-slate-700/50 cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-700/50 hover:border-gray-300 dark:hover:border-slate-600/60 transition-all"
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="flex items-start gap-3">
        <span className="text-[10px] font-mono text-gray-400 dark:text-slate-600 mt-0.5 shrink-0 pt-0.5">
          {num}
        </span>
        <span
          className={`text-[10px] px-2 py-0.5 rounded-full font-semibold shrink-0 ${sevStyle(issue.severity)}`}
        >
          {issue.severity}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm text-slate-200 leading-relaxed">{issue.description}</p>
          {issue.element_selector && (
            <p className="text-[10px] font-mono text-gray-400 dark:text-slate-500 mt-1 truncate bg-gray-100 dark:bg-slate-800/60 px-2 py-0.5 rounded">
              {issue.element_selector}
            </p>
          )}
          <div className="flex gap-3 mt-1.5">
            <span className="text-[10px] text-slate-500 capitalize font-medium">{issue.type}</span>
            {issue.breakpoint && (
              <span className="text-[10px] text-slate-500">{issue.breakpoint}px</span>
            )}
          </div>

          {expanded && issue.ai_suggestion && (
            <div className="mt-3">
              <div className="text-xs bg-violet-500/10 border border-violet-500/20 text-violet-300 px-3 py-2.5 rounded-lg leading-relaxed">
                <span className="font-semibold text-violet-400">AI Suggestion: </span>
                {issue.ai_suggestion}
              </div>
            </div>
          )}
        </div>
        <svg
          className={`w-3.5 h-3.5 text-gray-400 dark:text-slate-600 shrink-0 mt-0.5 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
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
          className="w-full flex items-center justify-between px-3 py-2 hover:bg-slate-700/30 transition-colors text-left rounded-lg"
        >
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-widest">
              {typeLabel(typeName)}
            </span>
            <span className="text-[10px] text-gray-500 dark:text-slate-600 bg-gray-200 dark:bg-slate-700/50 px-1.5 py-0.5 rounded-full">
              {issues.length}
            </span>
          </div>
          <svg
            className={`w-3.5 h-3.5 text-slate-600 transition-transform ${open ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
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
      defaultOpen={false}
      header={(open, toggle) => (
        <button
          onClick={toggle}
          className="w-full flex items-center justify-between px-5 py-4 bg-gray-100 dark:bg-slate-700/40 hover:bg-gray-200 dark:hover:bg-slate-700/60 transition-colors text-left border-b border-gray-200 dark:border-slate-700/60"
        >
          <div className="flex items-center gap-3">
            <span className="bg-gradient-to-br from-violet-600 to-indigo-600 text-white text-xs font-bold rounded-lg w-7 h-7 flex items-center justify-center shadow-lg shadow-violet-500/20">
              {pageNumber}
            </span>
            <span className="font-semibold text-gray-900 dark:text-white text-sm">
              {pageLabel(pageName)}
            </span>
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                issues.length > 0
                  ? "bg-red-500/10 text-red-400 border-red-500/25"
                  : "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
              }`}
            >
              {issues.length} issue{issues.length !== 1 ? "s" : ""}
            </span>
            {critCount > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/25 font-semibold">
                {critCount} critical
              </span>
            )}
            {majorCount > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/25 font-semibold">
                {majorCount} major
              </span>
            )}
          </div>
          <svg
            className={`w-4 h-4 text-gray-400 dark:text-slate-500 transition-transform ${open ? "rotate-180" : ""}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        </button>
      )}
    >
      <div className="flex gap-5 p-5">
        {/* Left: full-page screenshot */}
        <div className="w-[300px] shrink-0">
          <div className="sticky top-4">
            <div className="text-[10px] font-semibold text-gray-500 dark:text-slate-500 uppercase tracking-widest mb-2">
              Screenshot
            </div>
            <div className="border border-gray-200 dark:border-slate-700/60 rounded-xl overflow-hidden bg-gray-50 dark:bg-slate-800/40">
              {bestCapture?.image_url ? (
                <img
                  src={captureUrl(bestCapture.image_url)}
                  alt={`${pageLabel(pageName)} screenshot`}
                  className="w-full object-contain"
                  style={{ maxHeight: "800px" }}
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-48 text-gray-400 dark:text-slate-500 text-sm gap-2">
                  <svg className="w-8 h-8 text-gray-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
                  </svg>
                  No screenshot
                </div>
              )}
            </div>
            {bestCapture && (
              <div className="text-[10px] text-gray-400 dark:text-slate-600 mt-1.5 text-center">
                {bestCapture.breakpoint}px breakpoint
              </div>
            )}
          </div>
        </div>

        {/* Right: issues list grouped by type */}
        <div className="flex-1 min-w-0 space-y-3">
          {issues.length === 0 ? (
            <div className="text-center py-10">
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-3">
                <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <p className="text-sm font-medium text-emerald-400">No issues on this page</p>
            </div>
          ) : (
            <>
              {/* Show types that have issues */}
              {orderedTypes.map((typeName) => (
                <TypeSubsection
                  key={typeName}
                  typeName={typeName}
                  issues={byType[typeName]}
                  numberPrefix={`${pageNumber}`}
                  startIdx={typeOffsets[typeName]}
                />
              ))}
              {/* Show "no issues" message for standard types that are absent */}
              {typeOrder.filter((t) => !orderedTypes.includes(t)).map((typeName) => (
                <div
                  key={typeName}
                  className="bg-gray-50 dark:bg-slate-800/30 rounded-xl border border-gray-200 dark:border-slate-700/40 px-4 py-3 flex items-center gap-2"
                >
                  <svg className="w-4 h-4 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-xs font-medium text-emerald-400">
                    No {typeLabel(typeName).toLowerCase()} issues found
                  </span>
                </div>
              ))}
            </>
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
    <div className="border border-gray-200 dark:border-slate-700/60 rounded-2xl overflow-hidden">
      <Collapsible
        defaultOpen={false}
        header={(open, toggle) => (
          <button
            onClick={toggle}
            className="w-full flex items-center justify-between px-5 py-4 bg-gray-100 dark:bg-slate-700/40 hover:bg-gray-200 dark:hover:bg-slate-700/60 transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-sm">
                ♿
              </div>
              <span className="font-semibold text-gray-900 dark:text-white text-sm">
                {sectionNum}. ADA / Accessibility Issues
              </span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                  items.length > 0
                    ? "bg-red-500/10 text-red-400 border-red-500/25"
                    : "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
                }`}
              >
                {items.length} issue{items.length !== 1 ? "s" : ""}
              </span>
            </div>
            <svg
              className={`w-4 h-4 text-gray-400 dark:text-slate-500 transition-transform ${open ? "rotate-180" : ""}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
        )}
      >
        <div className="p-4 space-y-4">
          {Object.entries(byPage).map(([page, pageItems]) => {
            sub++;
            return (
              <div
                key={page}
                className="border border-gray-200 dark:border-slate-700/50 rounded-xl p-3 space-y-2"
              >
                <h4 className="text-xs font-semibold text-gray-600 dark:text-slate-400 mb-2">
                  {sectionNum}.{sub} {pageLabel(page)}
                </h4>
                {pageItems.map((item, idx) => (
                  <div
                    key={item.id}
                    className="p-2.5 bg-gray-50 dark:bg-slate-700/30 rounded-lg border border-gray-200 dark:border-slate-700/50 text-sm"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-mono text-gray-400 dark:text-slate-600 pt-0.5 shrink-0">
                        {sectionNum}.{sub}.{idx + 1}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-semibold shrink-0 ${sevStyle(item.severity)}`}
                      >
                        {item.severity}
                      </span>
                      <div className="min-w-0">
                        <p className="text-gray-800 dark:text-slate-200 text-sm">{item.description}</p>
                        {item.wcag && (
                          <p className="text-xs text-blue-400 mt-0.5">
                            WCAG: {item.wcag}
                          </p>
                        )}
                        {item.element && (
                          <p className="text-[10px] text-gray-400 dark:text-slate-500 font-mono mt-0.5 truncate bg-gray-100 dark:bg-slate-800/50 px-2 py-0.5 rounded">
                            {item.element}
                          </p>
                        )}
                        {item.help_text && (
                          <p className="text-xs text-gray-500 dark:text-slate-400 mt-1 leading-relaxed">
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
            <p className="text-sm text-gray-400 dark:text-slate-500 text-center py-4">
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
    <div className="border border-gray-200 dark:border-slate-700/60 rounded-2xl overflow-hidden">
      <Collapsible
        defaultOpen={false}
        header={(open, toggle) => (
          <button
            onClick={toggle}
            className="w-full flex items-center justify-between px-5 py-4 bg-gray-100 dark:bg-slate-700/40 hover:bg-gray-200 dark:hover:bg-slate-700/60 transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-sm">
                🔗
              </div>
              <span className="font-semibold text-gray-900 dark:text-white text-sm">
                {sectionNum}. Link & Button Audit
              </span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                  issueItems.length > 0
                    ? "bg-red-500/10 text-red-400 border-red-500/25"
                    : "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
                }`}
              >
                {issueItems.length} issue{issueItems.length !== 1 ? "s" : ""}
              </span>
            </div>
            <svg
              className={`w-4 h-4 text-gray-400 dark:text-slate-500 transition-transform ${open ? "rotate-180" : ""}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
        )}
      >
        <div className="p-4 space-y-4">
          {Object.entries(byPage).map(([page, pageItems]) => (
            <div
              key={page}
              className="border border-gray-200 dark:border-slate-700/50 rounded-xl p-3 space-y-1"
            >
              <h4 className="text-xs font-semibold text-slate-400 mb-2 flex items-center justify-between">
                <span>{pageLabel(page)}</span>
                <span className="text-slate-500 font-normal">
                  {pageItems.length} link{pageItems.length !== 1 ? "s" : ""}
                </span>
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-gray-500 dark:text-slate-500 border-b border-gray-200 dark:border-slate-700/60">
                      <th className="py-1.5 pr-3">Type</th>
                      <th className="py-1.5 pr-3">Text</th>
                      <th className="py-1.5 pr-3">Destination</th>
                      <th className="py-1.5 pr-3">Has href</th>
                      <th className="py-1.5">Issue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((item) => (
                      <tr
                        key={item.id}
                        className={`border-b border-gray-100 dark:border-slate-700/40 ${
                          item.issue ? "bg-red-500/5" : ""
                        }`}
                      >
                        <td className="py-1.5 pr-3 font-mono text-gray-500 dark:text-slate-400">
                          {item.element_type}
                        </td>
                        <td className="py-1.5 pr-3 max-w-[150px] truncate text-gray-700 dark:text-slate-300">
                          {item.text || "\u2014"}
                        </td>
                        <td className="py-1.5 pr-3 max-w-[200px] truncate text-blue-400">
                          {item.destination || item.href || "\u2014"}
                        </td>
                        <td className="py-1.5 pr-3 text-gray-700 dark:text-slate-300">
                          {item.has_href ? "✓" : "✗"}
                        </td>
                        <td className="py-1.5 text-red-400">
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
            <p className="text-sm text-gray-400 dark:text-slate-500 text-center py-4">
              No links audited
            </p>
          )}
        </div>
      </Collapsible>
    </div>
  );
};

// ---------- SEO Section ----------

interface SeoItem {
  id: number;
  page: string;
  test: string;
  label: string;
  passed: boolean;
  value: string;
  recommendation?: string;
  severity?: string;
}

const SeoSection = ({ items, sectionNum }: { items: SeoItem[]; sectionNum: number }) => {
  const passed = items.filter((i) => i.passed).length;
  const failed = items.filter((i) => !i.passed).length;
  const grouped = groupBy(items, (i) => i.page);

  return (
    <div className="border border-gray-200 dark:border-slate-700/60 rounded-2xl overflow-hidden">
      <Collapsible
        defaultOpen={false}
        header={(open, toggle) => (
          <button onClick={toggle} className="w-full flex items-center justify-between px-5 py-4 bg-gray-100 dark:bg-slate-700/40 hover:bg-gray-200 dark:hover:bg-slate-700/60 text-left border-b border-gray-200 dark:border-slate-700/60 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-sm">🔍</div>
              <span className="font-semibold text-gray-900 dark:text-white text-sm">{sectionNum}. SEO Analysis</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 font-semibold">{passed} passed</span>
              {failed > 0 && <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/25 font-semibold">{failed} issues</span>}
            </div>
            <svg className={`w-4 h-4 text-gray-400 dark:text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
        )}
      >
        <div className="p-4 space-y-4">
          {Object.entries(grouped).map(([page, pageItems]) => (
            <div key={page}>
              <h4 className="text-[10px] font-semibold text-gray-500 dark:text-slate-500 uppercase tracking-widest mb-2">{pageLabel(page)}</h4>
              <div className="space-y-1.5">
                {pageItems.map((item) => (
                  <div key={item.id} className={`flex items-start gap-3 px-3 py-2.5 rounded-xl text-sm border ${item.passed ? "bg-emerald-500/5 border-emerald-500/15" : "bg-red-500/5 border-red-500/15"}`}>
                    <span className="mt-0.5 shrink-0">{item.passed ? "✅" : "❌"}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-800 dark:text-slate-200 text-xs">{item.label}</span>
                        {item.severity && !item.passed && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${sevStyle(item.severity)}`}>{item.severity}</span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 dark:text-slate-500 mt-0.5">{item.value}</p>
                      {item.recommendation && <p className="text-xs text-orange-400 mt-0.5">{item.recommendation}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {items.length === 0 && <p className="text-sm text-gray-400 dark:text-slate-500 text-center py-4">No SEO data</p>}
        </div>
      </Collapsible>
    </div>
  );
};

// ---------- Performance Section ----------

interface PerfItem {
  id: number;
  page: string;
  load_time_ms: number;
  dom_ready_ms: number;
  ttfb_ms: number;
  total_resources: number;
  total_size_bytes: number;
  js_count: number;
  js_size_bytes: number;
  css_count: number;
  css_size_bytes: number;
  img_count: number;
  img_size_bytes: number;
  dom_nodes: number;
  issues: Array<{ test: string; label: string; severity: string; value: string; recommendation: string }>;
}

const fmtBytes = (b: number) => b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`;
const fmtMs = (ms: number) => ms > 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;

const PerfSection = ({ items, sectionNum }: { items: PerfItem[]; sectionNum: number }) => {
  const totalIssues = items.reduce((s, i) => s + (i.issues?.length ?? 0), 0);

  return (
    <div className="border border-gray-200 dark:border-slate-700/60 rounded-2xl overflow-hidden">
      <Collapsible
        defaultOpen={false}
        header={(open, toggle) => (
          <button onClick={toggle} className="w-full flex items-center justify-between px-5 py-4 bg-gray-100 dark:bg-slate-700/40 hover:bg-gray-200 dark:hover:bg-slate-700/60 text-left border-b border-gray-200 dark:border-slate-700/60 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-lg bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center text-sm">⚡</div>
              <span className="font-semibold text-gray-900 dark:text-white text-sm">{sectionNum}. Performance</span>
              {totalIssues > 0 && <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/25 font-semibold">{totalIssues} issues</span>}
            </div>
            <svg className={`w-4 h-4 text-gray-400 dark:text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
        )}
      >
        <div className="p-4 space-y-4">
          {items.map((p) => (
            <div key={p.id}>
              <h4 className="text-[10px] font-semibold text-gray-500 dark:text-slate-500 uppercase tracking-widest mb-3">{pageLabel(p.page)}</h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                <div className="bg-gray-100 dark:bg-slate-700/40 rounded-xl px-3 py-2.5 text-center border border-gray-200 dark:border-slate-700/50">
                  <div className={`text-lg font-bold ${p.load_time_ms > 5000 ? "text-red-400" : p.load_time_ms > 3000 ? "text-orange-400" : "text-emerald-400"}`}>{fmtMs(p.load_time_ms)}</div>
                  <div className="text-[10px] text-gray-500 dark:text-slate-500 uppercase mt-0.5">Load Time</div>
                </div>
                <div className="bg-gray-100 dark:bg-slate-700/40 rounded-xl px-3 py-2.5 text-center border border-gray-200 dark:border-slate-700/50">
                  <div className={`text-lg font-bold ${p.ttfb_ms > 600 ? "text-orange-400" : "text-emerald-400"}`}>{fmtMs(p.ttfb_ms)}</div>
                  <div className="text-[10px] text-gray-500 dark:text-slate-500 uppercase mt-0.5">TTFB</div>
                </div>
                <div className="bg-gray-100 dark:bg-slate-700/40 rounded-xl px-3 py-2.5 text-center border border-gray-200 dark:border-slate-700/50">
                  <div className={`text-lg font-bold ${p.total_size_bytes > 5*1024*1024 ? "text-red-400" : "text-gray-900 dark:text-white"}`}>{fmtBytes(p.total_size_bytes)}</div>
                  <div className="text-[10px] text-gray-500 dark:text-slate-500 uppercase mt-0.5">Page Size</div>
                </div>
                <div className="bg-gray-100 dark:bg-slate-700/40 rounded-xl px-3 py-2.5 text-center border border-gray-200 dark:border-slate-700/50">
                  <div className="text-lg font-bold text-gray-900 dark:text-white">{p.total_resources}</div>
                  <div className="text-[10px] text-gray-500 dark:text-slate-500 uppercase mt-0.5">Requests</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-[10px] text-gray-500 dark:text-slate-500 mb-3 px-1">
                <div>JS: {p.js_count} files ({fmtBytes(p.js_size_bytes)})</div>
                <div>CSS: {p.css_count} files ({fmtBytes(p.css_size_bytes)})</div>
                <div>Images: {p.img_count} ({fmtBytes(p.img_size_bytes)})</div>
              </div>
              {p.issues?.length > 0 && (
                <div className="space-y-1.5">
                  {p.issues.map((issue, idx) => (
                    <div key={idx} className="bg-orange-500/5 border border-orange-500/15 rounded-xl px-3 py-2.5 text-sm">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${sevStyle(issue.severity)}`}>{issue.severity}</span>
                        <span className="font-medium text-gray-800 dark:text-slate-200 text-xs">{issue.label}: {issue.value}</span>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">{issue.recommendation}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {items.length === 0 && <p className="text-sm text-gray-400 dark:text-slate-500 text-center py-4">No performance data</p>}
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
  hasDesignComparison?: boolean;
}

const ScoreCard = ({ score, threshold, issues, accCount, testMode, hasDesignComparison }: ScoreCardProps) => {
  const passed = score !== null && score >= threshold;
  const critCount = issues.filter((i) => i.severity === "critical").length;
  const majorCount = issues.filter((i) => i.severity === "major").length;
  const minorCount = issues.filter(
    (i) => i.severity !== "critical" && i.severity !== "major"
  ).length;

  // Progress bar width
  const barWidth = score !== null ? Math.min(score, 100) : 0;

  const ringColor = score === null ? "stroke-gray-300 dark:stroke-slate-700" : passed ? "stroke-emerald-500" : "stroke-red-500";
  const circumference = 2 * Math.PI * 52;
  const dashOffset = score !== null ? circumference * (1 - score / 100) : circumference;

  return (
    <div className="bg-white dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/60 rounded-2xl p-6 backdrop-blur-sm">
      <div className="flex items-center gap-8">
        {/* Score ring */}
        <div className="relative shrink-0 w-32 h-32">
          <svg className="w-32 h-32 -rotate-90" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="52" fill="none" strokeWidth="8" className="stroke-gray-200 dark:stroke-slate-800" />
            <circle
              cx="60" cy="60" r="52"
              fill="none"
              strokeWidth="8"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              strokeLinecap="round"
              className={`transition-all duration-1000 ${ringColor}`}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-3xl font-bold leading-none ${
              score === null ? "text-slate-500" : passed ? "text-emerald-400" : "text-red-400"
            }`}>
              {score !== null ? score : "—"}
            </span>
            <span className="text-xs text-gray-400 dark:text-slate-600 mt-0.5">/100</span>
          </div>
        </div>

        {/* Details */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-3">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">QA Results</h2>
            {score !== null && (
              <span className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-semibold border ${
                passed
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
                  : "bg-red-500/10 text-red-400 border-red-500/25"
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${passed ? "bg-emerald-400" : "bg-red-400"}`} />
                {passed ? "QA Passed" : "QA Failed"}
              </span>
            )}
            {testMode === "ai" && !hasDesignComparison && (
              <span className="text-xs px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/25 font-semibold">
                AI Mode
              </span>
            )}
            {hasDesignComparison && (
              <span className="text-xs px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/25 font-semibold">
                Design Comparison
              </span>
            )}
          </div>

          {/* Progress bar */}
          {score !== null && (
            <div className="w-full bg-gray-200 dark:bg-slate-700 rounded-full h-1.5 mb-4">
              <div
                className={`h-1.5 rounded-full transition-all duration-1000 ${
                  passed
                    ? "bg-gradient-to-r from-emerald-500 to-teal-500"
                    : "bg-gradient-to-r from-red-500 to-rose-500"
                }`}
                style={{ width: `${barWidth}%` }}
              />
            </div>
          )}

          <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
            {[
              { label: "Threshold", value: `${threshold}%`, color: "text-gray-700 dark:text-slate-300" },
              { label: "Total", value: issues.length, color: "text-gray-700 dark:text-slate-300" },
              { label: "Critical", value: critCount, color: critCount > 0 ? "text-red-400" : "text-slate-500" },
              { label: "Major", value: majorCount, color: majorCount > 0 ? "text-orange-400" : "text-slate-500" },
              { label: "Minor", value: minorCount, color: minorCount > 0 ? "text-yellow-400" : "text-slate-500" },
              { label: "ADA", value: accCount, color: accCount > 0 ? "text-blue-400" : "text-slate-500" },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-gray-100 dark:bg-slate-700/40 rounded-xl px-3 py-2 text-center border border-gray-200 dark:border-slate-700/50">
                <p className={`text-base font-bold ${color}`}>{value}</p>
                <p className="text-[10px] text-gray-500 dark:text-slate-500 uppercase mt-0.5">{label}</p>
              </div>
            ))}
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
  const [showPromptBuilder, setShowPromptBuilder] = useState(false);

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

  const { data: comparisonsData } = useQuery<ComparisonItem[]>({
    queryKey: ["comparisons", runId],
    queryFn: () => getComparisons(runId).then((r) => r.data),
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

  const { data: seoData } = useQuery<SeoItem[]>({
    queryKey: ["seo", runId],
    queryFn: () => getSeo(runId).then((r) => r.data),
    enabled: !!runId,
  });

  const { data: perfData } = useQuery<PerfItem[]>({
    queryKey: ["performance", runId],
    queryFn: () => getPerformance(runId).then((r) => r.data),
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
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <div className="w-8 h-8 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
        <p className="text-gray-500 dark:text-slate-400 text-sm">Loading results...</p>
      </div>
    );
  }
  if (runError || !run) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <p className="text-red-400 text-sm font-medium">Failed to load run results.</p>
      </div>
    );
  }

  // ---------- Derived data ----------

  const score =
    run.overall_score != null ? Math.round(run.overall_score) : null;
  const threshold = projectData?.pass_threshold ?? 90;
  const issues: Issue[] = allIssues ?? [];
  const captures: Capture[] = capturesData ?? [];
  const comparisons: ComparisonItem[] = comparisonsData ?? [];
  const accItems: AccessibilityItem[] = accData ?? [];

  // Check if any page used design comparison mode
  const hasDesignComparison =
    (run.page_configs?.some((pc) => pc.mode === "design") ?? false) ||
    captures.some((c) => c.source === "design");
  const linkItems: LinkAuditItem[] = linkData ?? [];
  const seoItems: SeoItem[] = seoData ?? [];
  const perfItems: PerfItem[] = perfData ?? [];

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

  // Show all tested pages (not just those with issues)
  const pagesWithIssues = pageList;

  // Determine which sections were actually run
  // test_types is null → Full QA → show everything
  const runTypes = run.test_types ? new Set(run.test_types.split(",")) : null;
  const showAda = runTypes === null || runTypes.has("ada");
  const showLinkAudit = runTypes === null || runTypes.has("link_audit");
  const showSeo = runTypes === null || runTypes.has("seo");
  const showPerf = runTypes === null || runTypes.has("performance");

  // Section numbering: pages first, then only sections that were run
  let sectionCounter = pagesWithIssues.length;
  const accSectionNum = showAda ? ++sectionCounter : 0;
  const linkSectionNum = showLinkAudit ? ++sectionCounter : 0;
  const seoSectionNum = showSeo ? ++sectionCounter : 0;
  const perfSectionNum = showPerf ? ++sectionCounter : 0;

  // Label map for display
  const TEST_LABELS: Record<string, string> = {
    qa: "QA Test",
    functional: "Functionality",
    ada: "ADA",
    seo: "SEO",
    performance: "Performance",
    link_audit: "Link Audit",
  };

  return (
    <div className="space-y-6">
      {/* Score Card */}
      <ScoreCard
        score={score}
        threshold={threshold}
        issues={issues}
        accCount={accItems.length}
        testMode={run.test_mode}
        hasDesignComparison={hasDesignComparison}
      />

      {/* Custom Run badge — only shown when test_types is set */}
      {run.test_types && (
        <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl px-4 py-2.5 flex items-center gap-3 text-sm">
          <span className="font-semibold text-indigo-600 dark:text-indigo-300">⚙️ Custom Run</span>
          <span className="text-indigo-400 dark:text-indigo-700">·</span>
          <span className="text-indigo-500 dark:text-indigo-400 text-xs">
            Tests selected:{" "}
            {run.test_types
              .split(",")
              .map((t) => TEST_LABELS[t] ?? t)
              .join(", ")}
          </span>
        </div>
      )}

      {/* Summary bar */}
      <div className="bg-gray-50 dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/60 rounded-xl px-5 py-3 flex items-center justify-between backdrop-blur-sm">
        <div className="flex items-center gap-4 text-sm">
          <span className="text-gray-500 dark:text-slate-500">
            Pages:{" "}
            <strong className="text-gray-800 dark:text-slate-200">{pageList.length}</strong>
          </span>
          <span className="text-gray-300 dark:text-slate-700">|</span>
          <span className="text-gray-500 dark:text-slate-500">
            Issues:{" "}
            <strong className="text-gray-800 dark:text-slate-200">{issues.length}</strong>
          </span>
          <span className="text-gray-300 dark:text-slate-700">|</span>
          <span className="text-xs text-gray-400 dark:text-slate-600">
            {pageList.filter((p) => (issuesByPage[p]?.length ?? 0) > 0).length} page{pageList.filter((p) => (issuesByPage[p]?.length ?? 0) > 0).length !== 1 ? "s" : ""} affected
          </span>
        </div>
        {issues.length > 0 && (
          <button
            onClick={() => setShowPromptBuilder(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 rounded-lg hover:from-violet-700 hover:to-indigo-700 shadow-lg shadow-violet-500/20 transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            Generate Fix Prompt
          </button>
        )}
      </div>

      {/* Visual Comparison Section — shown when design captures exist */}
      {hasDesignComparison && (() => {
        // Get unique pages that have design captures
        const designPages = [...new Set(captures.filter((c) => c.source === "design").map((c) => c.page))];
        return designPages.map((pageName) => {
          // Find best breakpoint (largest) for both sources
          const shopifyCapture = captures
            .filter((c) => c.page === pageName && c.source === "shopify")
            .sort((a, b) => b.breakpoint - a.breakpoint)[0];
          const designCapture = captures
            .filter((c) => c.page === pageName && c.source === "design")
            .sort((a, b) => b.breakpoint - a.breakpoint)[0];
          const comparison = comparisons
            .filter((c) => c.page === pageName)
            .sort((a, b) => b.breakpoint - a.breakpoint)[0];

          if (!shopifyCapture && !designCapture) return null;

          return (
            <div
              key={`comparison-${pageName}`}
              className="border border-gray-200 dark:border-slate-700/60 rounded-2xl overflow-hidden bg-white dark:bg-slate-800/30 backdrop-blur-sm"
            >
              <div className="px-5 py-4 bg-gray-100 dark:bg-slate-700/40 border-b border-gray-200 dark:border-slate-700/60">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="bg-gradient-to-br from-blue-600 to-cyan-600 text-white text-xs font-bold rounded-lg w-7 h-7 flex items-center justify-center shadow-lg shadow-blue-500/20">
                      VS
                    </span>
                    <span className="font-semibold text-gray-900 dark:text-white text-sm">
                      Visual Comparison — {pageName === "home" ? "Homepage" : `/${pageName}`}
                    </span>
                  </div>
                  {comparison && comparison.ssim_score != null && (
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                        comparison.ssim_score >= 0.95
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
                          : comparison.ssim_score >= 0.8
                          ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/25"
                          : "bg-red-500/10 text-red-400 border-red-500/25"
                      }`}>
                        SSIM: {(comparison.ssim_score * 100).toFixed(1)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>
              <div className="p-5">
                <SideBySideViewer
                  designImageUrl={designCapture?.image_url ? captureUrl(designCapture.image_url) : undefined}
                  shopifyImageUrl={shopifyCapture?.image_url ? captureUrl(shopifyCapture.image_url) : undefined}
                  diffOverlayUrl={comparison?.heatmap_url ? captureUrl(comparison.heatmap_url) : undefined}
                />
                {/* Breakpoint selector */}
                {(() => {
                  const breakpoints = [...new Set(
                    captures.filter((c) => c.page === pageName && c.source === "design").map((c) => c.breakpoint)
                  )].sort((a, b) => b - a);
                  if (breakpoints.length <= 1) return null;
                  return (
                    <div className="mt-4 flex items-center gap-2">
                      <span className="text-xs text-gray-500 dark:text-slate-400">All breakpoints:</span>
                      {breakpoints.map((bp) => {
                        const comp = comparisons.find((c) => c.page === pageName && c.breakpoint === bp);
                        return (
                          <span key={bp} className="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300">
                            {bp}px {comp?.ssim_score != null ? `(${(comp.ssim_score * 100).toFixed(1)}%)` : ""}
                          </span>
                        );
                      })}
                    </div>
                  );
                })()}

                {/* Written differences for this page */}
                {(() => {
                  const pageIssues = issues.filter((i) => i.page === pageName);
                  if (pageIssues.length === 0) return null;
                  return (
                    <div className="mt-6 border-t border-gray-200 dark:border-slate-700/60 pt-5">
                      <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <svg className="w-4 h-4 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                        </svg>
                        Differences Found ({pageIssues.length})
                      </h4>
                      <div className="space-y-3">
                        {pageIssues.map((issue) => (
                          <div
                            key={issue.id}
                            className="bg-gray-50 dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/50 rounded-xl px-4 py-3"
                          >
                            <div className="flex items-start gap-3">
                              <span className={`mt-0.5 shrink-0 text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                                SEVERITY_STYLES[issue.severity] ?? "bg-gray-500/10 text-gray-400 border border-gray-500/25"
                              }`}>
                                {issue.severity}
                              </span>
                              <div className="flex-1 min-w-0">
                                {issue.element_selector && (
                                  <p className="text-xs font-semibold text-gray-700 dark:text-slate-300 mb-1">
                                    {issue.element_selector}
                                  </p>
                                )}
                                <p className="text-xs text-gray-600 dark:text-slate-400 leading-relaxed">
                                  {issue.description}
                                </p>
                                {issue.ai_suggestion && (
                                  <div className="mt-2 bg-emerald-50 dark:bg-emerald-500/5 border border-emerald-200 dark:border-emerald-500/20 rounded-lg px-3 py-2">
                                    <p className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wide mb-0.5">Suggested Fix</p>
                                    <p className="text-xs text-emerald-700 dark:text-emerald-300 font-mono">{issue.ai_suggestion}</p>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>
          );
        });
      })()}

      {/* Page-by-page sections */}
      {pagesWithIssues.map((pageName, idx) => (
        <div
          key={pageName}
          className="border border-gray-200 dark:border-slate-700/60 rounded-2xl overflow-hidden bg-white dark:bg-slate-800/30 backdrop-blur-sm"
        >
          <PageSection
            pageName={pageName}
            pageNumber={idx + 1}
            issues={issuesByPage[pageName] ?? []}
            captures={captures}
          />
        </div>
      ))}

      {/* Accessibility Section — hidden when ADA test was not selected */}
      {showAda && <AccessibilitySection items={accItems} sectionNum={accSectionNum} />}

      {/* Link Audit Section — hidden when Link & Button Audit was not selected */}
      {showLinkAudit && <LinkAuditSection items={linkItems} sectionNum={linkSectionNum} />}

      {/* SEO Section — hidden when SEO test was not selected */}
      {showSeo && <SeoSection items={seoItems} sectionNum={seoSectionNum} />}

      {/* Performance Section — hidden when Performance test was not selected */}
      {showPerf && <PerfSection items={perfItems} sectionNum={perfSectionNum} />}

      {/* No issues at all */}
      {issues.length === 0 && accItems.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <div className="text-4xl mb-3">&#10003;</div>
          <p className="text-lg font-medium">No issues found</p>
          <p className="text-sm mt-1">Your site looks great!</p>
        </div>
      )}

      {/* Prompt Builder Modal */}
      {showPromptBuilder && (
        <PromptBuilder
          runId={runId}
          issues={issues}
          accItems={accItems}
          projectName={projectData?.name}
          shopifyUrl={projectData?.shopify_url}
          onClose={() => setShowPromptBuilder(false)}
        />
      )}
    </div>
  );
};

export default RunResults;
