import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getProject, updateProject } from "../api/projects";
import { listRuns, startRun } from "../api/runs";
import RunQAModal from "../components/runs/RunQAModal";

interface Run {
  id: number;
  status: string;
  overall_score?: number;
  created_at: string;
  run_number?: number;
}

interface Project {
  id: number;
  name: string;
  shopify_url: string;
  source_type?: string;
  source_url: string;
}

type Tab = "runs" | "settings";

const STATUS_CONFIG: Record<string, { dot: string; bg: string; text: string; border: string; label: string }> = {
  completed: { dot: "bg-emerald-400",             bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/25", label: "Completed" },
  running:   { dot: "bg-blue-400 animate-pulse",  bg: "bg-blue-500/10",   text: "text-blue-400",   border: "border-blue-500/25",   label: "Running"   },
  pending:   { dot: "bg-amber-400 animate-pulse", bg: "bg-amber-500/10",  text: "text-amber-400",  border: "border-amber-500/25",  label: "Pending"   },
  failed:    { dot: "bg-red-400",                 bg: "bg-red-500/10",    text: "text-red-400",    border: "border-red-500/25",    label: "Failed"    },
  cancelled: { dot: "bg-slate-500",               bg: "bg-gray-100 dark:bg-slate-700/50",  text: "text-gray-500 dark:text-slate-400",  border: "border-gray-300 dark:border-slate-600",     label: "Cancelled" },
};

const scoreColor = (s: number) =>
  s >= 90 ? "text-emerald-600 dark:text-emerald-400" : s >= 70 ? "text-amber-600 dark:text-amber-400" : "text-red-600 dark:text-red-400";
const scoreRing = (s: number) =>
  s >= 90 ? "stroke-emerald-500" : s >= 70 ? "stroke-amber-500" : "stroke-red-500";

const AVATAR_COLORS = [
  "from-violet-500 to-indigo-600",
  "from-emerald-500 to-teal-600",
  "from-rose-500 to-pink-600",
  "from-amber-500 to-orange-600",
  "from-blue-500 to-cyan-600",
];
const getAvatarColor = (name: string) =>
  AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];

const ProjectDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projectId = parseInt(id ?? "0", 10);

  const [activeTab, setActiveTab] = useState<Tab>("runs");
  const [settingsForm, setSettingsForm] = useState<Partial<Project>>({});
  const [editMode, setEditMode] = useState(false);
  const [showRunModal, setShowRunModal] = useState(false);

  const { data: project, isLoading: projectLoading, isError: projectError } = useQuery<Project>({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId).then((res) => res.data),
    enabled: !!projectId,
  });

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ["runs", projectId],
    queryFn: () => listRuns(projectId, 1).then((res) => res.data),
    enabled: !!projectId,
    refetchInterval: 10000,
  });

  const runMutation = useMutation({
    mutationFn: ({ pages, testMode, testTypes }: { pages: string; testMode: "design" | "ai"; testTypes?: string[] }) =>
      startRun(projectId, pages || undefined, testMode, testTypes),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["runs", projectId] });
      setShowRunModal(false);
      navigate(`/runs/${res.data.id}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => updateProject(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setEditMode(false);
    },
  });

  const runs: Run[] = runsData?.items ?? [];
  const activeRun = runs.find((r) => r.status === "running" || r.status === "pending");

  if (projectLoading) {
    return (
      <div className="p-8 flex flex-col items-center justify-center min-h-[400px] gap-4">
        <div className="w-8 h-8 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
        <p className="text-gray-500 dark:text-slate-400 text-sm">Loading project...</p>
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <div className="p-8 flex flex-col items-center justify-center min-h-[400px] gap-4">
        <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        </div>
        <p className="text-red-400 font-medium">Project not found or failed to load.</p>
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-1.5 text-sm text-violet-400 hover:text-violet-300 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Back to Projects
        </button>
      </div>
    );
  }

  const avatarColor = getAvatarColor(project.name);
  const completedRuns = runs.filter((r) => r.status === "completed" && r.overall_score != null);
  const avgScore = completedRuns.length > 0
    ? Math.round(completedRuns.reduce((s, r) => s + (r.overall_score ?? 0), 0) / completedRuns.length)
    : null;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${avatarColor} flex items-center justify-center shrink-0 shadow-lg mt-0.5`}>
            <span className="text-lg font-bold text-white">{project.name[0]?.toUpperCase()}</span>
          </div>
          <div>
            <button
              onClick={() => navigate("/projects")}
              className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800 dark:text-slate-500 dark:hover:text-slate-300 mb-1.5 transition-colors group"
            >
              <svg className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
              </svg>
              Projects
            </button>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">{project.name}</h1>
            <p className="text-sm text-gray-600 dark:text-slate-500 mt-0.5 truncate max-w-sm">{project.shopify_url}</p>
          </div>
        </div>

        {activeTab === "runs" && (
          <button
            onClick={() => setShowRunModal(true)}
            disabled={!!activeRun || runMutation.isPending}
            className="shrink-0 flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl hover:from-violet-700 hover:to-indigo-700 shadow-lg shadow-violet-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            title={activeRun ? "A run is already in progress" : ""}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
            </svg>
            {runMutation.isPending ? "Starting..." : "Run QA"}
          </button>
        )}
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-3 gap-4">
        {[
          {
            label: "Total Runs",
            value: runs.length,
            icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75z",
            color: "text-gray-900 dark:text-white",
          },
          {
            label: "Avg Score",
            value: avgScore != null ? `${avgScore}%` : "—",
            icon: "M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z",
            color: avgScore != null ? scoreColor(avgScore) : "text-slate-500",
          },
          {
            label: "Active Run",
            value: activeRun ? "Live" : "None",
            icon: "M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z",
            color: activeRun ? "text-blue-500 dark:text-blue-400" : "text-gray-400 dark:text-slate-500",
          },
        ].map(({ label, value, icon, color }) => (
          <div key={label} className="bg-white dark:bg-slate-800/50 rounded-2xl border border-gray-200 dark:border-slate-700/60 p-4">
            <div className="flex items-center gap-2 mb-2">
              <svg className="w-4 h-4 text-gray-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
              </svg>
              <p className="text-[10px] font-semibold text-gray-500 dark:text-slate-500 uppercase tracking-widest">{label}</p>
            </div>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Active run banner */}
      {activeRun && (
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-2xl px-5 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse shrink-0" />
            <span className="text-sm font-medium text-blue-600 dark:text-blue-300">
              QA Run #{activeRun.run_number ?? activeRun.id} is in progress...
            </span>
          </div>
          <Link
            to={`/runs/${activeRun.id}`}
            className="flex items-center gap-1.5 text-xs font-semibold text-blue-400 hover:text-blue-300 transition-colors"
          >
            View Progress
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
          </Link>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/60 rounded-xl p-1 w-fit">
        {([
          { key: "runs", label: "Runs", icon: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75z" },
          { key: "settings", label: "Settings", icon: "M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" },
        ] as { key: Tab; label: string; icon: string }[]).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.key
                ? "bg-violet-600 text-white shadow-lg shadow-violet-500/20"
                : "text-gray-500 hover:text-gray-900 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d={tab.icon} />
            </svg>
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Runs Tab ── */}
      {activeTab === "runs" && (
        <div className="space-y-3">
          {runsLoading && (
            <div className="flex flex-col items-center justify-center py-16 gap-4">
              <div className="w-7 h-7 rounded-full border-2 border-violet-500/30 border-t-violet-500 animate-spin" />
              <p className="text-gray-500 dark:text-slate-400 text-sm">Loading runs...</p>
            </div>
          )}

          {!runsLoading && runs.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-14 h-14 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mb-4">
                <svg className="w-7 h-7 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">No runs yet</h3>
              <p className="text-gray-500 dark:text-slate-500 text-sm mb-6">Start your first QA run to see results here.</p>
              <button
                onClick={() => setShowRunModal(true)}
                disabled={runMutation.isPending}
                className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl hover:from-violet-700 hover:to-indigo-700 shadow-lg shadow-violet-500/25 disabled:opacity-50 transition-all"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
                </svg>
                Run QA
              </button>
            </div>
          )}

          {!runsLoading && runs.length > 0 && runs.map((run: Run) => {
            const cfg = STATUS_CONFIG[run.status] ?? STATUS_CONFIG.cancelled;
            const score = run.overall_score != null ? Math.round(run.overall_score) : null;
            const circumference = 2 * Math.PI * 14;
            const dashOffset = score != null ? circumference * (1 - score / 100) : circumference;

            return (
              <Link
                key={run.id}
                to={`/runs/${run.id}`}
                className="group flex items-center gap-4 px-5 py-4 bg-white dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/60 rounded-2xl hover:bg-gray-50 dark:hover:bg-slate-800/70 hover:border-gray-300 dark:hover:border-slate-600/60 transition-all"
              >
                {/* Score ring */}
                <div className="relative w-10 h-10 shrink-0">
                  {score != null ? (
                    <>
                      <svg className="w-10 h-10 -rotate-90" viewBox="0 0 32 32">
                        <circle cx="16" cy="16" r="14" fill="none" strokeWidth="3" className="stroke-gray-200 dark:stroke-slate-800" />
                        <circle
                          cx="16" cy="16" r="14"
                          fill="none" strokeWidth="3"
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

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-800 dark:text-slate-200 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
                      Run #{run.run_number ?? run.id}
                    </span>
                    <span className={`inline-flex items-center gap-1.5 text-[10px] px-2 py-0.5 rounded-full font-semibold border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
                      <span className={`w-1 h-1 rounded-full ${cfg.dot}`} />
                      {cfg.label}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-slate-500 mt-0.5">
                    {new Date(run.created_at).toLocaleDateString("en-US", {
                      year: "numeric", month: "short", day: "numeric",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </p>
                </div>

                <svg className="w-4 h-4 text-gray-300 dark:text-slate-600 group-hover:text-violet-500 dark:group-hover:text-violet-400 transition-colors shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
              </Link>
            );
          })}
        </div>
      )}

      {/* ── Settings Tab ── */}
      {activeTab === "settings" && (
        <div className="max-w-5xl">
          {!editMode ? (
            <div className="bg-white dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/60 rounded-2xl p-6 space-y-5">
              {[
                { label: "Shopify URL", value: project.shopify_url },
                { label: "Reference URL", value: project.source_url, breakAll: true },
              ].map(({ label, value, breakAll }) => (
                <div key={label}>
                  <p className="text-[10px] font-semibold text-gray-400 dark:text-slate-500 uppercase tracking-widest mb-1.5">{label}</p>
                  <p className={`text-sm text-gray-700 dark:text-slate-200 ${breakAll ? "break-all" : ""}`}>
                    {value || <span className="text-gray-300 dark:text-slate-600 italic">Not set</span>}
                  </p>
                </div>
              ))}
              <div className="pt-2 border-t border-gray-200 dark:border-slate-700/50">
                <button
                  onClick={() => {
                    setSettingsForm({ shopify_url: project.shopify_url, source_url: project.source_url });
                    setEditMode(true);
                  }}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-violet-400 border border-violet-500/30 rounded-xl bg-violet-500/10 hover:bg-violet-500/20 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
                  </svg>
                  Edit Settings
                </button>
              </div>
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                updateMutation.mutate(settingsForm as Record<string, unknown>);
              }}
              className="bg-white dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700/60 rounded-2xl p-6 space-y-5"
            >
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300">Shopify URL</label>
                <input
                  type="url"
                  value={settingsForm.shopify_url ?? ""}
                  onChange={(e) => setSettingsForm((p) => ({ ...p, shopify_url: e.target.value }))}
                  className="w-full px-3.5 py-2.5 border border-gray-300 dark:border-slate-700 rounded-xl text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 bg-white dark:bg-slate-800/60 focus:bg-white dark:focus:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500 transition-all"
                />
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300">Source URL</label>
                <input
                  type="url"
                  value={settingsForm.source_url ?? ""}
                  onChange={(e) => setSettingsForm((p) => ({ ...p, source_url: e.target.value }))}
                  className="w-full px-3.5 py-2.5 border border-gray-300 dark:border-slate-700 rounded-xl text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-slate-500 bg-white dark:bg-slate-800/60 focus:bg-white dark:focus:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500 transition-all"
                />
              </div>
              <div className="flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={updateMutation.isPending}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-gradient-to-r from-violet-600 to-indigo-600 rounded-xl hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 shadow-lg shadow-violet-500/20 transition-all"
                >
                  {updateMutation.isPending ? (
                    <>
                      <div className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      Saving...
                    </>
                  ) : "Save Changes"}
                </button>
                <button
                  type="button"
                  onClick={() => setEditMode(false)}
                  className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-100 hover:text-gray-900 dark:text-slate-300 dark:border-slate-700 dark:hover:bg-slate-700/50 dark:hover:text-white transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Run QA Modal */}
      {showRunModal && (
        <RunQAModal
          onConfirm={(pages, testMode, testTypes) =>
            runMutation.mutate({ pages, testMode, testTypes })
          }
          onCancel={() => setShowRunModal(false)}
          isLoading={runMutation.isPending}
        />
      )}
    </div>
  );
};

export default ProjectDetailPage;
