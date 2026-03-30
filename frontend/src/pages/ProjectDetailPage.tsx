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
  source_type: string;
  source_url: string;
}

type Tab = "runs" | "settings";

const statusColor = (status: string) => {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-800";
    case "running":
      return "bg-blue-100 text-blue-800";
    case "failed":
      return "bg-red-100 text-red-800";
    case "cancelled":
      return "bg-gray-100 text-gray-800";
    default:
      return "bg-yellow-100 text-yellow-800";
  }
};

const ProjectDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projectId = parseInt(id ?? "0", 10);

  const [activeTab, setActiveTab] = useState<Tab>("runs");
  const [settingsForm, setSettingsForm] = useState<Partial<Project>>({});
  const [editMode, setEditMode] = useState(false);
  const [showRunModal, setShowRunModal] = useState(false);

  const {
    data: project,
    isLoading: projectLoading,
    isError: projectError,
  } = useQuery<Project>({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId).then((res) => res.data),
    enabled: !!projectId,
  });

  const {
    data: runsData,
    isLoading: runsLoading,
  } = useQuery({
    queryKey: ["runs", projectId],
    queryFn: () => listRuns(projectId, 1).then((res) => res.data),
    enabled: !!projectId,
    refetchInterval: 10000,
  });

  const runMutation = useMutation({
    mutationFn: ({
      pages,
      testMode,
      testTypes,
    }: {
      pages: string;
      testMode: "design" | "ai";
      testTypes?: string[];
    }) => startRun(projectId, pages || undefined, testMode, testTypes),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["runs", projectId] });
      setShowRunModal(false);
      navigate(`/runs/${res.data.id}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      updateProject(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setEditMode(false);
    },
  });

  const runs: Run[] = runsData?.items ?? [];
  const activeRun = runs.find((r) => r.status === "running" || r.status === "pending");

  if (projectLoading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="text-gray-500">Loading project...</div>
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <div className="p-8 flex flex-col items-center justify-center gap-4">
        <div className="text-red-500">Project not found or failed to load.</div>
        <button
          onClick={() => navigate("/")}
          className="text-indigo-600 hover:underline text-sm"
        >
          Back to Projects
        </button>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => navigate("/")}
            className="text-sm text-gray-500 hover:text-gray-700 mb-1 flex items-center gap-1"
          >
            &larr; Projects
          </button>
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
        </div>
        {activeTab === "runs" && (
          <button
            onClick={() => setShowRunModal(true)}
            disabled={!!activeRun || runMutation.isPending}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
            title={activeRun ? "A run is already in progress" : ""}
          >
            {runMutation.isPending ? "Starting..." : "Run QA"}
          </button>
        )}
      </div>

      {/* Active run banner */}
      {activeRun && (
        <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-pulse" />
            <span className="text-sm font-medium text-blue-800">
              QA Run #{activeRun.id} is in progress...
            </span>
          </div>
          <Link
            to={`/runs/${activeRun.id}`}
            className="text-sm font-medium text-blue-600 hover:text-blue-800 underline"
          >
            View Progress →
          </Link>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {([
            { key: "runs", label: "Runs" },
            { key: "settings", label: "Settings" },
          ] as { key: Tab; label: string }[]).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Runs Tab */}
      {activeTab === "runs" && (
        <div>
          {runsLoading && (
            <div className="text-gray-500 text-sm">Loading runs...</div>
          )}
          {!runsLoading && runs.length === 0 && (
            <div className="text-center py-16">
              <div className="text-gray-400 text-lg mb-2">No runs yet</div>
              <p className="text-gray-500 text-sm mb-6">
                Start your first QA run to see results here.
              </p>
              <button
                onClick={() => setShowRunModal(true)}
                disabled={runMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
              >
                Run QA
              </button>
            </div>
          )}
          {!runsLoading && runs.length > 0 && (
            <div className="space-y-3">
              {runs.map((run: Run) => (
                <Link
                  key={run.id}
                  to={`/runs/${run.id}`}
                  className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-indigo-300 hover:shadow-sm transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <span className="text-sm font-medium text-gray-900">
                        Run #{run.run_number ?? run.id}
                      </span>
                      <span
                        className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${statusColor(run.status)}`}
                      >
                        {run.status}
                        {(run.status === "running" || run.status === "pending") && (
                          <span className="ml-1 inline-block w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse align-middle" />
                        )}
                      </span>
                    </div>
                    <div className="flex items-center gap-6 text-sm text-gray-500">
                      {run.overall_score !== undefined && run.overall_score !== null && (
                        <span className="font-medium text-gray-700">Score: {Math.round(run.overall_score)}%</span>
                      )}
                      <span>
                        {new Date(run.created_at).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                      <span className="text-indigo-500 text-xs">View →</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === "settings" && (
        <div className="max-w-lg">
          {!editMode ? (
            <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  Shopify URL
                </div>
                <div className="text-sm text-gray-900">{project.shopify_url}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  Source Type
                </div>
                <div className="text-sm text-gray-900 capitalize">
                  {project.source_type}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                  Source URL
                </div>
                <div className="text-sm text-gray-900 break-all">
                  {project.source_url}
                </div>
              </div>
              <button
                onClick={() => {
                  setSettingsForm({
                    shopify_url: project.shopify_url,
                    source_url: project.source_url,
                  });
                  setEditMode(true);
                }}
                className="px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-600 rounded-lg hover:bg-indigo-50 transition-colors"
              >
                Edit Settings
              </button>
            </div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                updateMutation.mutate(settingsForm as Record<string, unknown>);
              }}
              className="bg-white border border-gray-200 rounded-lg p-6 space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Shopify URL
                </label>
                <input
                  type="url"
                  value={settingsForm.shopify_url ?? ""}
                  onChange={(e) =>
                    setSettingsForm((p) => ({ ...p, shopify_url: e.target.value }))
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Source URL
                </label>
                <input
                  type="url"
                  value={settingsForm.source_url ?? ""}
                  onChange={(e) =>
                    setSettingsForm((p) => ({ ...p, source_url: e.target.value }))
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div className="flex gap-3">
                <button
                  type="submit"
                  disabled={updateMutation.isPending}
                  className="flex-1 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
                >
                  {updateMutation.isPending ? "Saving..." : "Save Changes"}
                </button>
                <button
                  type="button"
                  onClick={() => setEditMode(false)}
                  className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
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
