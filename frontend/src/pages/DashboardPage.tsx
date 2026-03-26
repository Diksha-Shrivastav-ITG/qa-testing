import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listProjects } from "../api/projects";
import api from "../api/client";

interface Project {
  id: number;
  name: string;
  shopify_url: string;
  source_type: string;
}

interface Run {
  id: number;
  project_id: number;
  status: string;
  overall_score?: number;
  run_number?: number;
  started_at: string;
  test_mode?: string;
}

const statusStyle: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  running: "bg-blue-100 text-blue-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-500",
};

const DashboardPage = () => {
  const navigate = useNavigate();

  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(1, 50).then((r) => r.data),
  });

  // Fetch recent runs across all projects
  const { data: recentRuns } = useQuery<Run[]>({
    queryKey: ["recentRuns"],
    queryFn: async () => {
      const projects: Project[] = projectsData?.items ?? [];
      if (projects.length === 0) return [];
      const allRuns: Run[] = [];
      for (const p of projects.slice(0, 10)) {
        try {
          const res = await api.get(`/api/projects/${p.id}/runs?page=1&per_page=5`);
          const runs = (res.data?.items ?? []).map((r: Run) => ({ ...r, _projectName: p.name }));
          allRuns.push(...runs);
        } catch { /* skip */ }
      }
      return allRuns.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()).slice(0, 10);
    },
    enabled: !!(projectsData?.items?.length),
  });

  const projects: Project[] = projectsData?.items ?? [];
  const runs = recentRuns ?? [];

  const totalProjects = projects.length;
  const totalRuns = runs.length;
  const activeRuns = runs.filter((r) => r.status === "running").length;
  const avgScore = runs.filter((r) => r.overall_score != null).length > 0
    ? Math.round(runs.filter((r) => r.overall_score != null).reduce((s, r) => s + (r.overall_score ?? 0), 0) / runs.filter((r) => r.overall_score != null).length)
    : null;
  const _passRate = runs.filter((r) => r.status === "completed").length > 0
    ? Math.round((runs.filter((r) => r.status === "completed" && (r.overall_score ?? 0) >= 90).length / runs.filter((r) => r.status === "completed").length) * 100)
    : null;
  void _passRate; // reserved for future use

  const stats = [
    { label: "Total Projects", value: totalProjects, icon: "M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z", color: "from-violet-500 to-indigo-600", bg: "bg-violet-50" },
    { label: "Recent Runs", value: totalRuns, icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z", color: "from-blue-500 to-cyan-500", bg: "bg-blue-50" },
    { label: "Active Runs", value: activeRuns, icon: "M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z", color: "from-emerald-500 to-teal-500", bg: "bg-emerald-50" },
    { label: "Avg Score", value: avgScore !== null ? `${avgScore}%` : "--", icon: "M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z", color: "from-amber-500 to-orange-500", bg: "bg-amber-50" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Overview of your QA testing activity</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        {stats.map((stat) => (
          <div key={stat.label} className="bg-white rounded-2xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between mb-3">
              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center shadow-sm`}>
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d={stat.icon} />
                </svg>
              </div>
            </div>
            <div className="text-2xl font-bold text-gray-900">{stat.value}</div>
            <div className="text-xs text-gray-500 mt-0.5">{stat.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Runs */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">Recent QA Runs</h2>
            <span className="text-xs text-gray-400">{runs.length} runs</span>
          </div>
          <div className="divide-y divide-gray-50">
            {runs.length === 0 && (
              <div className="px-5 py-10 text-center text-sm text-gray-400">No runs yet. Start a QA run from a project.</div>
            )}
            {runs.map((run) => {
              const proj = projects.find((p) => p.id === run.project_id);
              return (
                <button
                  key={run.id}
                  onClick={() => navigate(`/runs/${run.id}`)}
                  className="w-full flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 truncate">{proj?.name ?? `Project #${run.project_id}`}</span>
                      <span className="text-xs text-gray-400">Run #{run.run_number ?? run.id}</span>
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {new Date(run.started_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    {run.overall_score != null && (
                      <span className={`text-sm font-bold ${run.overall_score >= 90 ? "text-emerald-600" : run.overall_score >= 70 ? "text-amber-600" : "text-red-600"}`}>
                        {Math.round(run.overall_score)}%
                      </span>
                    )}
                    <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${statusStyle[run.status] ?? "bg-gray-100 text-gray-500"}`}>
                      {run.status}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Quick Actions + Projects */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <div className="bg-white rounded-2xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Quick Actions</h2>
            <div className="space-y-2">
              <button
                onClick={() => navigate("/projects")}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-medium hover:shadow-lg hover:shadow-violet-500/25 transition-all"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                New Project
              </button>
              <button
                onClick={() => navigate("/projects")}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-200 text-gray-700 text-sm font-medium hover:bg-gray-50 transition-colors"
              >
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                </svg>
                View All Projects
              </button>
            </div>
          </div>

          {/* Projects List */}
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-900">Projects</h2>
            </div>
            <div className="divide-y divide-gray-50">
              {projects.length === 0 && (
                <div className="px-5 py-8 text-center text-sm text-gray-400">No projects yet</div>
              )}
              {projects.slice(0, 6).map((p) => (
                <button
                  key={p.id}
                  onClick={() => navigate(`/projects/${p.id}`)}
                  className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{p.name}</p>
                    <p className="text-xs text-gray-400 truncate">{p.shopify_url}</p>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                    p.source_type === "none" ? "bg-purple-100 text-purple-700" : p.source_type === "figma" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"
                  }`}>
                    {p.source_type === "none" ? "AI" : p.source_type}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
