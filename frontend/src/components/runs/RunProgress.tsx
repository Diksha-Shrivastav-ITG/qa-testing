import { useSSE } from "../../hooks/useSSE";

interface RunProgressProps {
  runId: number;
}

const STEP_ICONS: Record<string, string> = {
  discovery:    "M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z",
  capture:      "M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z",
  compare:      "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
  functional:   "M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z",
  accessibility:"M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z",
  link_audit:   "M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244",
  matching:     "M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5",
  scoring:      "M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z",
  completed:    "M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
};

const STEPS_ORDER = ["discovery", "capture", "compare", "functional", "accessibility", "link_audit", "matching", "scoring", "completed"];

const stepLabel = (step: string): string => {
  const labels: Record<string, string> = {
    discovery:    "Discovering pages",
    capture:      "Capturing screenshots",
    compare:      "Comparing designs (AI analysis)",
    functional:   "Running functional tests",
    accessibility:"ADA compliance checks",
    link_audit:   "Link & button audit",
    matching:     "Matching with previous run",
    scoring:      "Calculating score",
    completed:    "QA Complete",
    failed:       "QA Failed",
    cancelled:    "Run Cancelled",
  };
  return labels[step] ?? step.charAt(0).toUpperCase() + step.slice(1).replace(/_/g, " ");
};

const RunProgress = ({ runId }: RunProgressProps) => {
  const { progress, isComplete, error } = useSSE(runId);

  const pct = progress?.progress ?? 0;
  const isFailed = progress?.step === "failed";
  const currentStepIdx = STEPS_ORDER.indexOf(progress?.step ?? "");

  return (
    <div className="space-y-4">
      {/* Main progress card */}
      <div className="bg-white dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/60 rounded-2xl p-6 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">QA Run in Progress</h2>
            <p className="text-xs text-gray-500 dark:text-slate-500 mt-0.5">Real-time analysis underway</p>
          </div>
          {isComplete && (
            <span className={`inline-flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-full ${
              isFailed
                ? "bg-red-500/10 text-red-400 border border-red-500/20"
                : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isFailed ? "bg-red-400" : "bg-emerald-400"}`} />
              {isFailed ? "QA Failed" : "QA Complete"}
            </span>
          )}
        </div>

        {/* Big percentage + step */}
        <div className="flex items-center gap-5 mb-5">
          <div className="relative w-20 h-20 shrink-0">
            <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
              <circle cx="40" cy="40" r="34" fill="none" strokeWidth="6" className="stroke-gray-200 dark:stroke-slate-800" />
              <circle
                cx="40" cy="40" r="34"
                fill="none"
                strokeWidth="6"
                strokeDasharray={2 * Math.PI * 34}
                strokeDashoffset={2 * Math.PI * 34 * (1 - Math.min(100, Math.max(0, pct)) / 100)}
                strokeLinecap="round"
                className={`transition-all duration-500 ${isFailed ? "stroke-red-500" : "stroke-violet-500"}`}
              />
            </svg>
            <span className={`absolute inset-0 flex items-center justify-center text-lg font-bold ${isFailed ? "text-red-400" : "text-gray-900 dark:text-white"}`}>
              {Math.round(pct)}%
            </span>
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900 dark:text-white">
              {progress ? stepLabel(progress.step) : "Initializing..."}
            </p>
            {progress?.message && (
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-1 leading-relaxed">{progress.message}</p>
            )}
            {progress?.page && (
              <p className="text-xs text-gray-500 dark:text-slate-500 mt-1.5 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse shrink-0" />
                <span className="font-medium text-gray-700 dark:text-slate-300">{progress.page}</span>
                {progress.breakpoint && (
                  <span className="text-gray-500 dark:text-slate-500">@ {progress.breakpoint}px</span>
                )}
              </p>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full h-2 bg-gray-200 dark:bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isFailed
                ? "bg-gradient-to-r from-red-600 to-red-500"
                : "bg-gradient-to-r from-violet-600 to-indigo-500"
            }`}
            style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
          />
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 px-3 py-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            {error}
          </div>
        )}
      </div>

      {/* Step pipeline */}
      <div className="bg-white dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/60 rounded-2xl p-5 backdrop-blur-sm">
        <p className="text-[10px] font-semibold text-gray-500 dark:text-slate-500 uppercase tracking-widest mb-4">Pipeline</p>
        <div className="space-y-2">
          {STEPS_ORDER.filter(s => s !== "completed").map((step, idx) => {
            const isDone = currentStepIdx > idx;
            const isCurrent = currentStepIdx === idx;
            const iconPath = STEP_ICONS[step] ?? STEP_ICONS.scoring;

            return (
              <div
                key={step}
                className={`flex items-center gap-3 px-3 py-2 rounded-xl transition-colors ${
                  isCurrent
                    ? "bg-violet-500/10 border border-violet-500/20"
                    : isDone
                    ? "opacity-50"
                    : "opacity-30"
                }`}
              >
                <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${
                  isDone ? "bg-emerald-500/20" : isCurrent ? "bg-violet-500/20" : "bg-gray-200 dark:bg-slate-700"
                }`}>
                  {isDone ? (
                    <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  ) : (
                    <svg className={`w-3.5 h-3.5 ${isCurrent ? "text-violet-400" : "text-gray-400 dark:text-slate-500"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d={iconPath} />
                    </svg>
                  )}
                </div>
                <span className={`text-xs font-medium ${
                  isCurrent ? "text-violet-600 dark:text-violet-300" : isDone ? "text-gray-500 dark:text-slate-400" : "text-gray-300 dark:text-slate-600"
                }`}>
                  {stepLabel(step)}
                </span>
                {isCurrent && (
                  <span className="ml-auto flex gap-1">
                    {[0,1,2].map(i => (
                      <span key={i} className="w-1 h-1 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default RunProgress;
