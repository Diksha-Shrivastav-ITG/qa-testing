import { useSSE } from "../../hooks/useSSE";

interface RunProgressProps {
  runId: number;
}

const stepLabel = (step: string): string => {
  switch (step) {
    case "discovery":
      return "Discovering pages";
    case "capture":
      return "Capturing screenshots";
    case "compare":
      return "Comparing designs (AI analysis)";
    case "functional":
      return "Running functional tests";
    case "accessibility":
      return "ADA compliance checks";
    case "link_audit":
      return "Link & button audit";
    case "matching":
      return "Matching with previous run";
    case "scoring":
      return "Calculating score";
    case "completed":
      return "QA Complete";
    case "failed":
      return "QA Failed";
    case "cancelled":
      return "Run Cancelled";
    default:
      return step.charAt(0).toUpperCase() + step.slice(1).replace(/_/g, " ");
  }
};

const RunProgress = ({ runId }: RunProgressProps) => {
  const { progress, isComplete, error } = useSSE(runId);

  const pct = progress?.progress ?? 0;
  const isFailed = progress?.step === "failed";

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">QA Run Progress</h2>
        {isComplete && (
          <span
            className={`text-sm font-medium px-3 py-1 rounded-full ${
              isFailed
                ? "bg-red-100 text-red-700"
                : "bg-green-100 text-green-700"
            }`}
          >
            {isFailed ? "QA Failed" : "QA Complete"}
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full h-4 bg-gray-200 rounded overflow-hidden">
        <div
          className={`h-full transition-all duration-500 ${
            isFailed ? "bg-red-500" : "bg-blue-500"
          }`}
          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700">
          {progress ? stepLabel(progress.step) : "Initializing..."}
        </span>
        <span className="text-gray-500">{Math.round(pct)}%</span>
      </div>

      {progress?.message && (
        <p className="text-sm text-gray-500">{progress.message}</p>
      )}

      {progress?.page && (
        <p className="text-xs text-gray-400">
          Page: <span className="font-medium text-gray-600">{progress.page}</span>
          {progress.breakpoint && (
            <span className="ml-2">
              @ <span className="font-medium text-gray-600">{progress.breakpoint}px</span>
            </span>
          )}
        </p>
      )}

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}
    </div>
  );
};

export default RunProgress;
