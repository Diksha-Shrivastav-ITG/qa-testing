import { useState } from "react";

export interface Issue {
  id: number;
  type: string;
  severity: string;
  page?: string;
  breakpoint?: number;
  description: string;
  element?: string;
  selector?: string;
  location?: string;
  ai_suggestion?: string;
}

interface IssueCardProps {
  issue: Issue;
}

const severityBadge = (severity: string) => {
  switch (severity.toLowerCase()) {
    case "critical":
      return "bg-red-100 text-red-700 border border-red-200";
    case "major":
      return "bg-orange-100 text-orange-700 border border-orange-200";
    case "minor":
      return "bg-yellow-100 text-yellow-700 border border-yellow-200";
    default:
      return "bg-gray-100 text-gray-600 border border-gray-200";
  }
};

const typeIcon = (type: string) => {
  switch (type.toLowerCase()) {
    case "visual":
      return "👁";
    case "functional":
      return "⚙️";
    case "content":
      return "📝";
    default:
      return "🔍";
  }
};

const IssueCard = ({ issue }: IssueCardProps) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Severity badge */}
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-semibold shrink-0 capitalize ${severityBadge(
              issue.severity
            )}`}
          >
            {issue.severity}
          </span>

          {/* Type */}
          <span className="text-xs text-gray-500 shrink-0 flex items-center gap-1">
            <span>{typeIcon(issue.type)}</span>
            <span className="capitalize">{issue.type}</span>
          </span>

          <div className="flex-1 min-w-0">
            {/* Description */}
            <p className="text-sm text-gray-800 leading-snug">{issue.description}</p>

            {/* Page + breakpoint */}
            <div className="flex flex-wrap gap-3 mt-1.5 text-xs text-gray-400">
              {issue.page && (
                <span>
                  Page: <span className="text-gray-600 font-medium">{issue.page}</span>
                </span>
              )}
              {issue.breakpoint && (
                <span>
                  Breakpoint:{" "}
                  <span className="text-gray-600 font-medium">{issue.breakpoint}px</span>
                </span>
              )}
            </div>

            {/* AI suggestion */}
            {issue.ai_suggestion && (
              <div className="mt-2 px-3 py-2 bg-indigo-50 border border-indigo-100 rounded text-xs text-indigo-700">
                <span className="font-semibold">AI Suggestion: </span>
                {issue.ai_suggestion}
              </div>
            )}
          </div>

          {/* Expand toggle */}
          {(issue.location || issue.selector || issue.element) && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-gray-400 hover:text-gray-600 shrink-0 transition-colors"
              aria-label="Toggle details"
            >
              {expanded ? "▲" : "▼"}
            </button>
          )}
        </div>

        {/* Expanded details */}
        {expanded && (
          <div className="mt-3 pt-3 border-t border-gray-100 space-y-1.5">
            {issue.location && (
              <div className="text-xs">
                <span className="text-gray-500 font-medium">Location: </span>
                <span className="text-gray-700">{issue.location}</span>
              </div>
            )}
            {(issue.selector || issue.element) && (
              <div className="text-xs">
                <span className="text-gray-500 font-medium">Selector: </span>
                <code className="font-mono text-gray-700 bg-gray-50 px-1 py-0.5 rounded">
                  {issue.selector ?? issue.element}
                </code>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default IssueCard;
