import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listRuns } from "../../api/runs";

interface Run {
  id: number;
  status: string;
  score?: number;
  created_at: string;
}

interface RunsResponse {
  runs?: Run[];
}

interface RunHistoryProps {
  projectId: number;
}

const statusBadge = (status: string) => {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-800";
    case "running":
      return "bg-blue-100 text-blue-800";
    case "failed":
      return "bg-red-100 text-red-800";
    case "cancelled":
      return "bg-gray-100 text-gray-600";
    default:
      return "bg-yellow-100 text-yellow-800";
  }
};

const scoreColor = (score: number, prevScore?: number) => {
  if (prevScore === undefined) return "text-gray-700";
  if (score > prevScore) return "text-green-600";
  if (score < prevScore) return "text-red-600";
  return "text-gray-700";
};

const RunHistory = ({ projectId }: RunHistoryProps) => {
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery<RunsResponse | Run[]>({
    queryKey: ["runs", projectId],
    queryFn: () => listRuns(projectId, 1).then((res) => res.data),
    enabled: !!projectId,
  });

  const runs: Run[] = Array.isArray(data)
    ? data
    : (data as RunsResponse)?.runs ?? [];

  if (isLoading) {
    return (
      <div className="text-sm text-gray-500 py-6 text-center">
        Loading run history...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-sm text-red-500 py-6 text-center">
        Failed to load run history.
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="text-sm text-gray-400 py-8 text-center border border-dashed border-gray-200 rounded-lg">
        No runs yet for this project.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
        Run History
      </h3>

      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-3 top-4 bottom-4 w-px bg-gray-200" />

        <div className="space-y-2">
          {runs.map((run, index) => {
            const prevRun = runs[index + 1];
            const score =
              run.score !== undefined && run.score !== null
                ? Math.round(run.score)
                : null;
            const prevScore =
              prevRun?.score !== undefined && prevRun?.score !== null
                ? Math.round(prevRun.score!)
                : undefined;

            return (
              <div
                key={run.id}
                onClick={() => navigate(`/runs/${run.id}`)}
                className="relative pl-8 cursor-pointer group"
              >
                {/* Timeline dot */}
                <div className="absolute left-1.5 top-4 w-3 h-3 rounded-full border-2 border-white bg-gray-300 group-hover:bg-indigo-500 transition-colors" />

                <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 flex items-center justify-between hover:border-indigo-300 hover:shadow-sm transition-all">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-gray-900">
                      Run #{run.id}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${statusBadge(
                        run.status
                      )}`}
                    >
                      {run.status}
                    </span>
                  </div>

                  <div className="flex items-center gap-6 text-sm">
                    {score !== null && (
                      <span
                        className={`font-semibold ${scoreColor(
                          score,
                          prevScore
                        )}`}
                      >
                        {score}%
                        {prevScore !== undefined && score !== prevScore && (
                          <span className="text-xs ml-1 font-normal">
                            {score > prevScore
                              ? `(+${score - prevScore})`
                              : `(${score - prevScore})`}
                          </span>
                        )}
                      </span>
                    )}
                    <span className="text-gray-400 text-xs">
                      {new Date(run.created_at).toLocaleDateString("en-US", {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default RunHistory;
