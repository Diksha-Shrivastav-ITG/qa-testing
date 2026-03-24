import { useQuery } from "@tanstack/react-query";
import api from "../../api/client";

interface ComparisonData {
  resolved: number;
  still_open: number;
  new_issues: number;
}

interface RunComparisonProps {
  runId: number;
  prevRunId: number;
}

const fetchComparison = (runId: number, prevRunId: number) =>
  api
    .get<ComparisonData>(`/api/runs/${runId}/compare/${prevRunId}`)
    .then((res) => res.data);

const RunComparison = ({ runId, prevRunId }: RunComparisonProps) => {
  const { data, isLoading, isError } = useQuery<ComparisonData>({
    queryKey: ["comparison", runId, prevRunId],
    queryFn: () => fetchComparison(runId, prevRunId),
    enabled: !!runId && !!prevRunId,
  });

  if (isLoading) {
    return (
      <div className="text-sm text-gray-500 py-4 text-center">
        Loading comparison...
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="text-sm text-red-500 py-4 text-center">
        Failed to load comparison data.
      </div>
    );
  }

  const cards = [
    {
      label: "Resolved",
      count: data.resolved,
      color: "bg-green-50 border-green-200",
      textColor: "text-green-700",
      countColor: "text-green-600",
    },
    {
      label: "Still Open",
      count: data.still_open,
      color: "bg-yellow-50 border-yellow-200",
      textColor: "text-yellow-700",
      countColor: "text-yellow-600",
    },
    {
      label: "New Issues",
      count: data.new_issues,
      color: "bg-red-50 border-red-200",
      textColor: "text-red-700",
      countColor: "text-red-600",
    },
  ];

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Comparison
        </h3>
        <span className="text-xs text-gray-400">
          Run #{runId} vs Run #{prevRunId}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {cards.map(({ label, count, color, textColor, countColor }) => (
          <div
            key={label}
            className={`border rounded-lg p-4 text-center ${color}`}
          >
            <div className={`text-3xl font-bold ${countColor}`}>{count}</div>
            <div className={`text-xs font-medium mt-1 ${textColor}`}>
              {label}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RunComparison;
