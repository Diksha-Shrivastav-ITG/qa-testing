import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getRun, cancelRun } from "../api/runs";
import RunProgress from "../components/runs/RunProgress";
import RunResults from "../components/runs/RunResults";

interface Run {
  id: number;
  status: string;
  overall_score?: number;
  project_id?: number;
  started_at: string;
  run_number?: number;
}

const RunDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const runId = parseInt(id ?? "0", 10);

  const {
    data: run,
    isLoading,
    isError,
  } = useQuery<Run>({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId).then((res) => res.data),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Poll every 5s while running — ensures UI updates even if SSE disconnects
      return status === "running" || status === "pending" ? 5000 : false;
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
    },
  });

  const handleDownload = (format: "pdf" | "html") => {
    const token = localStorage.getItem("token");
    const endpoint = format === "pdf" ? "pdf" : "html";
    const url = `http://localhost:8000/api/runs/${runId}/report/${endpoint}${
      token ? `?token=${encodeURIComponent(token)}` : ""
    }`;
    window.open(url, "_blank");
  };

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="text-gray-500">Loading run...</div>
      </div>
    );
  }

  if (isError || !run) {
    return (
      <div className="p-8 flex flex-col items-center justify-center gap-4">
        <div className="text-red-500">Run not found or failed to load.</div>
        <button
          onClick={() => navigate(-1)}
          className="text-indigo-600 hover:underline text-sm"
        >
          Go back
        </button>
      </div>
    );
  }

  const isRunning = run.status === "running" || run.status === "pending";
  const isTerminal = run.status === "completed" || run.status === "failed" || run.status === "cancelled";

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="text-sm text-gray-500 hover:text-gray-700 mb-1 flex items-center gap-1"
          >
            &larr; Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Run #{run.run_number ?? run.id}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Started{" "}
            {new Date(run.started_at).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isRunning && (
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className="px-3 py-2 text-sm font-medium text-red-600 border border-red-300 rounded-lg hover:bg-red-50 disabled:opacity-60 transition-colors"
            >
              {cancelMutation.isPending ? "Cancelling..." : "Cancel"}
            </button>
          )}
          {isTerminal && run.status === "completed" && (
            <>
              <button
                onClick={() => handleDownload("pdf")}
                className="px-3 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Download PDF
              </button>
              <button
                onClick={() => handleDownload("html")}
                className="px-3 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Download HTML
              </button>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      {isRunning && <RunProgress runId={runId} />}
      {isTerminal && <RunResults runId={runId} />}

      {/* Cancelled state */}
      {run.status === "cancelled" && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
          <p className="text-gray-500 text-sm">This run was cancelled.</p>
        </div>
      )}
    </div>
  );
};

export default RunDetailPage;
