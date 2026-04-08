import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listProjects } from "../api/projects";
import api from "../api/client";
import { getMe } from "../api/auth";

interface Project {
  id: number;
  name: string;
  shopify_url: string;
  source_type: string;
  pass_threshold?: number;
}

interface Run {
  id: number;
  project_id: number;
  status: string;
  overall_score?: number;
  run_number?: number;
  started_at: string;
  test_mode?: string;
  _projectName?: string;
}

interface Issue {
  id: number;
  severity: "critical" | "major" | "minor";
  type: string;
  status: string;
}

const STATUS_CONFIG: Record<string, { dot: string; bg: string; text: string; label: string }> = {
  completed: { dot: "bg-emerald-500", bg: "bg-emerald-100 border border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/20", text: "text-emerald-700 dark:text-emerald-400", label: "Completed" },
  running:   { dot: "bg-blue-500 animate-pulse", bg: "bg-blue-100 border border-blue-200 dark:bg-blue-500/10 dark:border-blue-500/20", text: "text-blue-700 dark:text-blue-400", label: "Running" },
  failed:    { dot: "bg-red-500", bg: "bg-red-100 border border-red-200 dark:bg-red-500/10 dark:border-red-500/20", text: "text-red-700 dark:text-red-400", label: "Failed" },
  cancelled: { dot: "bg-gray-400", bg: "bg-gray-100 border border-gray-200 dark:bg-slate-500/10 dark:border-slate-500/20", text: "text-gray-600 dark:text-slate-400", label: "Cancelled" },
};

const scoreColor = (s: number) =>
  s >= 90 ? "text-emerald-600 dark:text-emerald-400" : s >= 70 ? "text-amber-600 dark:text-amber-400" : "text-red-600 dark:text-red-400";

const scoreRing = (s: number) =>
  s >= 90 ? "stroke-emerald-500" : s >= 70 ? "stroke-amber-500" : "stroke-red-500";

const scoreBg = (s: number) =>
  s >= 90 ? "from-emerald-400 to-teal-500" : s >= 70 ? "from-amber-400 to-orange-500" : "from-red-400 to-rose-500";

const DashboardPage = () => {
  const navigate = useNavigate();

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => getMe().then((r) => r.data),
    staleTime: Infinity,
  });

  const hour = new Date().getHours();
  const greetingWord = hour < 12 ? "Good Morning" : hour < 17 ? "Good Afternoon" : "Good Evening";
  const greeting = me?.name ? `${greetingWord}, ${me.name}` : greetingWord;

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(1, 50).then((r) => r.data),
  });

  const { data: recentRuns } = useQuery<Run[]>({
    queryKey: ["recentRuns", projectsData?.items?.map((p: Project) => p.id)],
    queryFn: async () => {
      const projects: Project[] = projectsData?.items ?? [];
      if (projects.length === 0) return [];
      const results = await Promise.all(
        projects.slice(0, 10).map((p: Project) =>
          api
            .get(`/api/projects/${p.id}/runs?page=1&per_page=5`)
            .then((res: { data: { items?: Run[] } }) =>
              (res.data?.items ?? []).map((r: Run) => ({ ...r, _projectName: p.name }))
            )
            .catch(() => [] as Run[])
        )
      );
      return results
        .flat()
        .sort((a: Run, b: Run) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
        .slice(0, 10);
    },
    enabled: !!(projectsData?.items?.length),
  });

  const projects: Project[] = projectsData?.items ?? [];
  const runs = recentRuns ?? [];

  const latestCompletedRun = runs.find((r) => r.status === "completed");

  const { data: issuesData } = useQuery<Issue[]>({
    queryKey: ["latestIssues", latestCompletedRun?.id],
    queryFn: async () => {
      const res = await api.get(`/api/runs/${latestCompletedRun?.id}/issues`);
      return res.data?.items ?? res.data ?? [];
    },
    enabled: !!latestCompletedRun?.id,
  });

  const issues = issuesData ?? [];

  const activeRuns = runs.filter((r) => r.status === "running").length;
  const completedRuns = runs.filter((r) => r.status === "completed");
  const scoredRuns = completedRuns.filter((r) => r.overall_score != null);
  const avgScore =
    scoredRuns.length > 0
      ? Math.round(scoredRuns.reduce((s, r) => s + (r.overall_score ?? 0), 0) / scoredRuns.length)
      : null;
  const passRate =
    scoredRuns.length > 0
      ? Math.round((scoredRuns.filter((r) => (r.overall_score ?? 0) >= 90).length / scoredRuns.length) * 100)
      : null;

  const criticalCount = issues.filter((i) => i.severity === "critical").length;
  const majorCount   = issues.filter((i) => i.severity === "major").length;
  const minorCount   = issues.filter((i) => i.severity === "minor").length;
  const totalIssues  = issues.length;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">

      {/* ── Welcome header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-violet-600 dark:text-violet-400 mb-0.5">{greeting}!</h1>
          <p className="text-sm text-gray-500 dark:text-slate-500 mt-0.5">
            {new Date().toLocaleDateString("en-IN", {
              weekday: "long", year: "numeric", month: "long", day: "numeric",
              timeZone: "Asia/Kolkata",
            })}
          </p>
        </div>
        <button
          onClick={() => navigate("/projects")}
          className="shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold hover:from-violet-700 hover:to-indigo-700 shadow-lg shadow-violet-500/25 hover:shadow-violet-500/40 transition-all"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Project
        </button>
      </div>

      {/* ── Metric cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">

        {/* QA Health Score */}
        <div className="bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 p-5 shadow-sm dark:shadow-none hover:shadow-md dark:hover:shadow-none hover:border-gray-300 dark:hover:bg-slate-800/70 dark:hover:border-slate-600/60 hover:-translate-y-0.5 transition-all duration-200">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[11px] font-semibold text-gray-500 dark:text-slate-500 uppercase tracking-widest">Health Score</p>
            <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${avgScore != null ? scoreBg(avgScore) : "from-gray-300 to-gray-400"} flex items-center justify-center shadow-sm`}>
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
              </svg>
            </div>
          </div>
          <p className={`text-3xl font-bold ${avgScore != null ? scoreColor(avgScore) : "text-slate-600"}`}>
            {avgScore != null ? `${avgScore}%` : "--"}
          </p>
          <p className="text-xs text-gray-500 dark:text-slate-500 mt-1">Avg across {scoredRuns.length} completed runs</p>
          {avgScore != null && (
            <div className="mt-3 h-1.5 bg-gray-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${scoreBg(avgScore)} transition-all duration-700`}
                style={{ width: `${avgScore}%` }}
              />
            </div>
          )}
        </div>

        {/* Issues Found */}
        <div className="bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 p-5 shadow-sm dark:shadow-none hover:shadow-md dark:hover:shadow-none hover:border-gray-300 dark:hover:bg-slate-800/70 dark:hover:border-slate-600/60 hover:-translate-y-0.5 transition-all duration-200">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[11px] font-semibold text-gray-500 dark:text-slate-500 uppercase tracking-widest">Issues Found</p>
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-rose-500 to-red-600 flex items-center justify-center shadow-sm">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
            </div>
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">{latestCompletedRun ? totalIssues : "--"}</p>
          <p className="text-xs text-gray-500 dark:text-slate-500 mt-1">From latest completed run</p>
          {latestCompletedRun && totalIssues > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {criticalCount > 0 && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-700 dark:text-red-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500" />{criticalCount} critical
                </span>
              )}
              {majorCount > 0 && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />{majorCount} major
                </span>
              )}
              {minorCount > 0 && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-700 dark:text-blue-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />{minorCount} minor
                </span>
              )}
            </div>
          )}
        </div>

        {/* Pass Rate */}
        <div className="bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 p-5 shadow-sm dark:shadow-none hover:shadow-md dark:hover:shadow-none hover:border-gray-300 dark:hover:bg-slate-800/70 dark:hover:border-slate-600/60 hover:-translate-y-0.5 transition-all duration-200">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[11px] font-semibold text-gray-500 dark:text-slate-500 uppercase tracking-widest">Pass Rate</p>
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-sm">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">{passRate != null ? `${passRate}%` : "--"}</p>
          <p className="text-xs text-gray-500 dark:text-slate-500 mt-1">Runs scoring ≥ 90%</p>
          {passRate != null && (
            <div className="mt-3 h-1.5 bg-gray-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-500 transition-all duration-700"
                style={{ width: `${passRate}%` }}
              />
            </div>
          )}
        </div>

        {/* Projects */}
        <div className="bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 p-5 shadow-sm dark:shadow-none hover:shadow-md dark:hover:shadow-none hover:border-gray-300 dark:hover:bg-slate-800/70 dark:hover:border-slate-600/60 hover:-translate-y-0.5 transition-all duration-200">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[11px] font-semibold text-gray-500 dark:text-slate-500 uppercase tracking-widest">Projects</p>
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-sm">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
            </div>
          </div>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">{projects.length}</p>
          {activeRuns > 0 ? (
            <p className="text-xs text-blue-400 mt-1 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              {activeRuns} test{activeRuns > 1 ? "s" : ""} running now
            </p>
          ) : (
            <p className="text-xs text-gray-500 dark:text-slate-500 mt-1">Active Shopify stores</p>
          )}
        </div>

      </div>

      {/* ── Main grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Recent Runs — 2 cols */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 dark:border-slate-700/50 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Recent QA Runs</h2>
              {activeRuns > 0 && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 text-[11px] font-medium border border-blue-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                  {activeRuns} live
                </span>
              )}
            </div>
            <button
              onClick={() => navigate("/projects")}
              className="text-xs text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 font-semibold transition-colors"
            >
              View all →
            </button>
          </div>

          <div className="divide-y divide-gray-100 dark:divide-slate-700/50">
            {runs.length === 0 ? (
              <div className="px-5 py-14 text-center">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500/10 to-indigo-500/10 border border-violet-500/20 flex items-center justify-center mx-auto mb-4">
                  <svg className="w-7 h-7 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75z" />
                  </svg>
                </div>
                <p className="text-sm font-medium text-gray-500 dark:text-slate-400">No runs yet</p>
                <p className="text-xs text-gray-500 dark:text-slate-500 mt-1">Create a project and start your first QA run</p>
                <button
                  onClick={() => navigate("/projects")}
                  className="mt-4 px-4 py-2 text-xs font-semibold text-violet-400 border border-violet-500/30 rounded-lg hover:bg-violet-500/10 transition-colors"
                >
                  Create Project
                </button>
              </div>
            ) : (
              runs.map((run) => {
                const proj = projects.find((p) => p.id === run.project_id);
                const cfg  = STATUS_CONFIG[run.status] ?? STATUS_CONFIG.cancelled;
                const score = run.overall_score != null ? Math.round(run.overall_score) : null;
                const circumference = 2 * Math.PI * 14;
                const dashOffset = score != null ? circumference * (1 - score / 100) : circumference;

                return (
                  <button
                    key={run.id}
                    onClick={() => navigate(`/runs/${run.id}`)}
                    className="w-full flex items-center gap-4 px-5 py-3.5 hover:bg-gray-100 dark:hover:bg-slate-700/40 transition-colors text-left group"
                  >
                    {/* Score ring */}
                    <div className="shrink-0 relative w-10 h-10">
                      {score != null ? (
                        <>
                          <svg className="w-10 h-10 -rotate-90" viewBox="0 0 32 32">
                            <circle cx="16" cy="16" r="14" fill="none" strokeWidth="3" className="stroke-gray-200 dark:stroke-slate-800" />
                            <circle
                              cx="16" cy="16" r="14"
                              fill="none"
                              strokeWidth="3"
                              strokeDasharray={circumference}
                              strokeDashoffset={dashOffset}
                              strokeLinecap="round"
                              className={`transition-all ${scoreRing(score)}`}
                            />
                          </svg>
                          <span className={`absolute inset-0 flex items-center justify-center text-[10px] font-bold ${scoreColor(score)}`}>
                            {score}
                          </span>
                        </>
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-gray-100 dark:bg-slate-700 flex items-center justify-center">
                          <span className="text-[10px] text-gray-400 dark:text-slate-500 font-medium">--</span>
                        </div>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-gray-800 dark:text-slate-200 truncate group-hover:text-violet-600 dark:group-hover:text-violet-300 transition-colors">
                          {run._projectName ?? proj?.name ?? `Project #${run.project_id}`}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-slate-500 shrink-0">#{run.run_number ?? run.id}</span>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-slate-500 mt-0.5">
                        {new Date(run.started_at).toLocaleDateString("en-IN", {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                          timeZone: "Asia/Kolkata",
                        })}
                      </p>
                    </div>

                    <div className="shrink-0 flex items-center gap-2">
                      <span className={`inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full font-medium ${cfg.bg} ${cfg.text}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                        {cfg.label}
                      </span>
                      <svg className="w-4 h-4 text-gray-400 dark:text-slate-600 group-hover:text-violet-500 dark:group-hover:text-violet-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                      </svg>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right column — 1 col */}
        <div className="space-y-5">

          {/* Issue Severity Breakdown */}
          <div className="bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 p-5 shadow-sm dark:shadow-none">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Issue Breakdown</h2>
              <span className="text-[11px] text-gray-500 dark:text-slate-500">Latest run</span>
            </div>

            {!latestCompletedRun ? (
              <div className="py-5 text-center text-xs text-gray-500 dark:text-slate-500">
                No completed runs yet
              </div>
            ) : totalIssues === 0 ? (
              <div className="py-5 text-center">
                <div className="w-10 h-10 rounded-full bg-emerald-100 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 flex items-center justify-center mx-auto mb-2">
                  <svg className="w-5 h-5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">All clear!</p>
                <p className="text-xs text-gray-500 dark:text-slate-500 mt-0.5">No issues in latest run</p>
              </div>
            ) : (
              <div className="space-y-3">
                {[
                  { label: "Critical", count: criticalCount, color: "bg-red-500",   textColor: "text-red-600 dark:text-red-400" },
                  { label: "Major",    count: majorCount,    color: "bg-amber-500", textColor: "text-amber-600 dark:text-amber-400" },
                  { label: "Minor",    count: minorCount,    color: "bg-blue-500",  textColor: "text-blue-600 dark:text-blue-400" },
                ].map(({ label, count, color, textColor }) => (
                  <div key={label}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-medium text-gray-600 dark:text-slate-400">{label}</span>
                      <span className={`text-xs font-bold ${textColor}`}>{count}</span>
                    </div>
                    <div className="h-1.5 bg-gray-200 dark:bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${color} transition-all duration-700`}
                        style={{ width: totalIssues > 0 ? `${(count / totalIssues) * 100}%` : "0%" }}
                      />
                    </div>
                  </div>
                ))}
                <div className="pt-3 border-t border-gray-200 dark:border-slate-700/50">
                  <button
                    onClick={() => navigate(`/runs/${latestCompletedRun.id}`)}
                    className="w-full text-xs text-center text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 font-semibold transition-colors"
                  >
                    View full report →
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Quick Actions */}
          <div className="bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 p-5 shadow-sm dark:shadow-none">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">Quick Actions</h2>
            <div className="space-y-2">
              <button
                onClick={() => navigate("/projects")}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-medium hover:from-violet-700 hover:to-indigo-700 shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                New Project
              </button>
              <button
                onClick={() => navigate("/projects")}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-200 dark:border-slate-700 text-gray-700 dark:text-slate-400 text-sm font-medium hover:bg-gray-100 dark:hover:bg-slate-700/50 hover:text-gray-900 dark:hover:text-slate-200 transition-colors"
              >
                <svg className="w-4 h-4 text-gray-500 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                </svg>
                Browse Projects
              </button>
            </div>
          </div>

          {/* Projects list */}
          <div className="bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 overflow-hidden shadow-sm dark:shadow-none">
            <div className="px-5 py-4 border-b border-gray-200 dark:border-slate-700/50 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Your Projects</h2>
              <button
                onClick={() => navigate("/projects")}
                className="text-xs text-violet-600 hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300 font-semibold transition-colors"
              >
                View all
              </button>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-slate-700/50">
              {projects.length === 0 ? (
                <div className="px-5 py-8 text-center text-sm text-gray-500 dark:text-slate-500">No projects yet</div>
              ) : (
                projects.slice(0, 5).map((p) => (
                  <button
                    key={p.id}
                    onClick={() => navigate(`/projects/${p.id}`)}
                    className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 dark:hover:bg-slate-700/40 transition-colors text-left group"
                  >
                    <div className="min-w-0 flex items-center gap-3">
                      <div className="w-7 h-7 rounded-lg bg-violet-100 dark:bg-gradient-to-br dark:from-violet-500/20 dark:to-indigo-500/20 border border-violet-200 dark:border-violet-500/20 flex items-center justify-center shrink-0">
                        <span className="text-xs font-bold text-violet-600 dark:text-violet-400">
                          {p.name[0]?.toUpperCase()}
                        </span>
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-800 dark:text-slate-200 truncate group-hover:text-violet-600 dark:group-hover:text-violet-300 transition-colors">
                          {p.name}
                        </p>
                        <p className="text-[11px] text-gray-500 dark:text-slate-500 truncate">{p.shopify_url}</p>
                      </div>
                    </div>
                    <span
                      className={`shrink-0 ml-2 text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                        p.source_type === "none"
                          ? "bg-violet-100 border-violet-200 text-violet-700 dark:bg-violet-500/10 dark:border-violet-500/20 dark:text-violet-400"
                          : p.source_type === "figma"
                          ? "bg-emerald-100 border-emerald-200 text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/20 dark:text-emerald-400"
                          : "bg-blue-100 border-blue-200 text-blue-700 dark:bg-blue-500/10 dark:border-blue-500/20 dark:text-blue-400"
                      }`}
                    >
                      {p.source_type === "none" ? "AI" : p.source_type}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
