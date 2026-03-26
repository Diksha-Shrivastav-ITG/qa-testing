import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listIssues } from "../../api/issues";
import IssueCard from "./IssueCard";
import type { Issue } from "./IssueCard";

interface IssueListProps {
  runId: number;
}

interface IssuesResponse {
  issues: Issue[];
  total?: number;
  page?: number;
  pages?: number;
}

const SEVERITY_OPTIONS = ["All", "critical", "major", "minor"];
const TYPE_OPTIONS = ["All", "visual", "functional", "content"];

const IssueList = ({ runId }: IssueListProps) => {
  const [severity, setSeverity] = useState("All");
  const [type, setType] = useState("All");
  const [page, setPage] = useState(1);

  const params = {
    severity: severity !== "All" ? severity : undefined,
    type: type !== "All" ? type : undefined,
    page,
  };

  const { data, isLoading, isError } = useQuery<IssuesResponse>({
    queryKey: ["issues", runId, severity, type, page],
    queryFn: () => listIssues(runId, params).then((res) => res.data),
    enabled: !!runId,
  });

  const issues: Issue[] = data?.issues ?? [];
  const totalPages = data?.pages ?? 1;

  const handleFilterChange = (field: "severity" | "type", value: string) => {
    setPage(1);
    if (field === "severity") setSeverity(value);
    else setType(value);
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Severity
          </label>
          <select
            value={severity}
            onChange={(e) => handleFilterChange("severity", e.target.value)}
            className="text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          >
            {SEVERITY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Type
          </label>
          <select
            value={type}
            onChange={(e) => handleFilterChange("type", e.target.value)}
            className="text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          >
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {data?.total !== undefined && (
          <span className="text-xs text-gray-400 ml-auto">
            {data.total} issue{data.total !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Issue cards */}
      {isLoading && (
        <div className="text-sm text-gray-500 py-8 text-center">Loading issues...</div>
      )}

      {isError && (
        <div className="text-sm text-red-500 py-8 text-center">
          Failed to load issues.
        </div>
      )}

      {!isLoading && !isError && issues.length === 0 && (
        <div className="text-sm text-gray-400 py-8 text-center border border-dashed border-gray-200 rounded-lg">
          No issues found
          {severity !== "All" || type !== "All" ? " for the selected filters" : ""}.
        </div>
      )}

      {!isLoading && !isError && issues.length > 0 && (
        <div className="space-y-2">
          {issues.map((issue) => (
            <IssueCard key={issue.id} issue={issue} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-xs font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-xs font-medium text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default IssueList;
