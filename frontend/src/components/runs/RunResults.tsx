import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getRun } from "../../api/runs";
import { listIssues } from "../../api/issues";
import BreakpointTabs from "../comparison/BreakpointTabs";
import SideBySideViewer from "../comparison/SideBySideViewer";

interface Issue {
  id: number;
  type: string;
  severity: string;
  page?: string;
  breakpoint?: number;
  description: string;
  element?: string;
}

interface RunData {
  id: number;
  status: string;
  score?: number;
  pages?: string[];
  threshold?: number;
  created_at: string;
}

interface IssuesData {
  issues: Issue[];
  total?: number;
}

const severityColor = (severity: string) => {
  switch (severity) {
    case "critical":
      return "bg-red-100 text-red-700";
    case "high":
      return "bg-orange-100 text-orange-700";
    case "medium":
      return "bg-yellow-100 text-yellow-700";
    case "low":
      return "bg-gray-100 text-gray-600";
    default:
      return "bg-gray-100 text-gray-600";
  }
};

interface PageSectionProps {
  pageName: string;
  issues: Issue[];
}

const PageSection = ({ pageName, issues }: PageSectionProps) => {
  const [open, setOpen] = useState(false);
  const [activeBreakpoint, setActiveBreakpoint] = useState(1280);

  const pageIssues = issues.filter((i) => !i.page || i.page === pageName);

  // Placeholder image paths — real URLs would come from backend storage
  const designImageUrl = undefined;
  const shopifyImageUrl = undefined;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <span className="font-medium text-gray-900 text-sm">{pageName}</span>
          {pageIssues.length > 0 && (
            <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded-full font-medium">
              {pageIssues.length} issue{pageIssues.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <span className="text-gray-400 text-sm">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="p-4 space-y-4">
          <BreakpointTabs
            activeBreakpoint={activeBreakpoint}
            onSelect={setActiveBreakpoint}
          />

          <SideBySideViewer
            designImageUrl={designImageUrl}
            shopifyImageUrl={shopifyImageUrl}
          />

          {/* Issues list */}
          {pageIssues.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-gray-700">Issues</h4>
              {pageIssues.map((issue) => (
                <div
                  key={issue.id}
                  className="flex items-start gap-3 p-3 bg-gray-50 rounded border border-gray-100"
                >
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${severityColor(issue.severity)}`}
                  >
                    {issue.severity}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm text-gray-800">{issue.description}</p>
                    {issue.element && (
                      <p className="text-xs text-gray-400 mt-0.5 font-mono truncate">
                        {issue.element}
                      </p>
                    )}
                    <div className="flex gap-3 mt-1">
                      <span className="text-xs text-gray-400">{issue.type}</span>
                      {issue.breakpoint && (
                        <span className="text-xs text-gray-400">
                          {issue.breakpoint}px
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {pageIssues.length === 0 && (
            <p className="text-sm text-gray-400">No issues found for this page.</p>
          )}
        </div>
      )}
    </div>
  );
};

interface RunResultsProps {
  runId: number;
}

const RunResults = ({ runId }: RunResultsProps) => {
  const {
    data: run,
    isLoading: runLoading,
    isError: runError,
  } = useQuery<RunData>({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId).then((res) => res.data),
    enabled: !!runId,
  });

  const { data: issuesData, isLoading: issuesLoading } = useQuery<IssuesData>({
    queryKey: ["issues", runId],
    queryFn: () => listIssues(runId).then((res) => res.data),
    enabled: !!runId,
  });

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

  const score = run.score !== undefined && run.score !== null ? Math.round(run.score) : null;
  const threshold = run.threshold ?? 90;
  const passed = score !== null && score >= threshold;
  const issues: Issue[] = issuesData?.issues ?? [];

  // Derive unique pages from issues or run.pages
  const pages: string[] =
    run.pages && run.pages.length > 0
      ? run.pages
      : Array.from(new Set(issues.map((i) => i.page ?? "Unknown").filter(Boolean)));

  if (pages.length === 0) {
    pages.push("Homepage");
  }

  return (
    <div className="space-y-6">
      {/* Score card */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 flex items-center gap-6">
        <div className="text-center">
          <div
            className={`text-5xl font-bold ${
              score === null ? "text-gray-400" : passed ? "text-green-600" : "text-red-600"
            }`}
          >
            {score !== null ? score : "—"}
          </div>
          <div className="text-xs text-gray-500 mt-1">Score</div>
        </div>
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
          </div>
          <div className="text-sm text-gray-500 space-y-0.5">
            <div>
              Total issues:{" "}
              <span className="font-medium text-gray-700">{issues.length}</span>
            </div>
            <div>
              Threshold:{" "}
              <span className="font-medium text-gray-700">{threshold}%</span>
            </div>
            <div>
              Status:{" "}
              <span
                className={`font-medium ${
                  run.status === "completed"
                    ? "text-green-700"
                    : run.status === "failed"
                    ? "text-red-700"
                    : "text-gray-700"
                }`}
              >
                {run.status}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Page sections */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Pages
        </h3>
        {pages.map((page) => (
          <PageSection
            key={page}
            pageName={page}
            issues={issues}
          />
        ))}
      </div>
    </div>
  );
};

export default RunResults;
