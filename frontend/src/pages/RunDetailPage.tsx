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

const STATUS_CONFIG: Record<string, { dot: string; bg: string; text: string; label: string }> = {
  completed: { dot: "bg-emerald-400", bg: "bg-emerald-500/10", text: "text-emerald-400", label: "Completed" },
  running:   { dot: "bg-blue-400 animate-pulse", bg: "bg-blue-500/10", text: "text-blue-400", label: "Running" },
  failed:    { dot: "bg-red-400", bg: "bg-red-500/10", text: "text-red-400", label: "Failed" },
  cancelled: { dot: "bg-slate-500", bg: "bg-gray-100 dark:bg-slate-700/50", text: "text-gray-500 dark:text-slate-400", label: "Cancelled" },
  pending:   { dot: "bg-amber-400 animate-pulse", bg: "bg-amber-500/10", text: "text-amber-400", label: "Pending" },
};

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
    const url = `/api/runs/${runId}/report/${endpoint}${
      token ? `?token=${encodeURIComponent(token)}` : ""
    }`;
    window.open(url, "_blank");
  };

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
          <p className="text-gray-400 dark:text-slate-400 text-sm">Loading run details...</p>
        </div>
      </div>
    );
  }

  if (isError || !run) {
    return (
      <div className="p-8 flex flex-col items-center justify-center min-h-[400px] gap-4">
        <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        </div>
        <p className="text-red-400 font-medium">Run not found or failed to load.</p>
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-violet-400 hover:text-violet-300 flex items-center gap-1.5 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Go back
        </button>
      </div>
    );
  }

  const isRunning = run.status === "running" || run.status === "pending";
  const isTerminal = run.status === "completed" || run.status === "failed" || run.status === "cancelled";
  const statusCfg = STATUS_CONFIG[run.status] ?? STATUS_CONFIG.cancelled;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 dark:text-slate-500 dark:hover:text-slate-300 mb-3 transition-colors group"
          >
            <svg className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
            Back
          </button>

          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">
              Run #{run.run_number ?? run.id}
            </h1>
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${statusCfg.bg} ${statusCfg.text} border border-current/20`}>
              <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot}`} />
              {statusCfg.label}
            </span>
          </div>

          <p className="text-sm text-gray-600 dark:text-slate-500">
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

        <div className="flex items-center gap-2 shrink-0">
          {isRunning && (
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className="px-3 py-2 text-sm font-medium text-red-400 border border-red-500/30 rounded-xl bg-red-500/10 hover:bg-red-500/20 disabled:opacity-50 transition-colors"
            >
              {cancelMutation.isPending ? "Cancelling..." : "Cancel Run"}
            </button>
          )}
          {isTerminal && run.status === "completed" && (
            <>
              <button
                onClick={() => handleDownload("pdf")}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-xl bg-gray-50 hover:bg-gray-100 hover:text-gray-900 dark:text-slate-300 dark:border-slate-700 dark:bg-slate-800/60 dark:hover:bg-slate-700/60 dark:hover:text-white transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                PDF
              </button>
              <button
                onClick={() => handleDownload("html")}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-xl bg-gray-50 hover:bg-gray-100 hover:text-gray-900 dark:text-slate-300 dark:border-slate-700 dark:bg-slate-800/60 dark:hover:bg-slate-700/60 dark:hover:text-white transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                </svg>
                HTML
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
        <div className="bg-white dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/60 rounded-2xl p-10 text-center">
          <div className="w-12 h-12 rounded-2xl bg-gray-100 dark:bg-slate-700/60 border border-gray-200 dark:border-slate-600 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-gray-400 dark:text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <p className="text-gray-700 dark:text-slate-300 font-medium">This run was cancelled.</p>
          <p className="text-gray-400 dark:text-slate-500 text-sm mt-1">No results to display.</p>
        </div>
      )}
    </div>
  );
};

export default RunDetailPage;
