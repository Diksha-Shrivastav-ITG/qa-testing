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

type Tab = "runs" | "test-cases" | "settings";

const TEST_CASES = [
  { id: "visual_ai", label: "Visual AI Analysis", desc: "AI reviews each page for layout, spacing, color, and design issues", category: "Visual", default: true },
  { id: "visual_comparison", label: "Design Comparison (SSIM)", desc: "Pixel-level comparison between Framer/Figma design and Shopify", category: "Visual", default: true },
  { id: "functional_add_to_cart", label: "Add to Cart Flow", desc: "Test that users can add products to cart and cart updates", category: "Functional", default: true },
  { id: "functional_checkout", label: "Checkout Flow", desc: "Test that users can reach the checkout page", category: "Functional", default: true },
  { id: "functional_search", label: "Search Functionality", desc: "Test search opens, accepts input, and shows results", category: "Functional", default: true },
  { id: "functional_mobile_menu", label: "Mobile Menu", desc: "Test hamburger menu opens and shows navigation", category: "Functional", default: true },
  { id: "functional_collection_filter", label: "Collection Filters", desc: "Test that filters update the product grid", category: "Functional", default: false },
  { id: "functional_newsletter", label: "Newsletter Signup", desc: "Verify email signup form exists and is functional", category: "Functional", default: true },
  { id: "link_check", label: "Broken Link Check", desc: "Check all links for 404s and broken URLs", category: "Links & Buttons", default: true },
  { id: "image_check", label: "Broken Image Check", desc: "Check all images for missing sources and alt text", category: "Links & Buttons", default: true },
  { id: "link_audit", label: "Link & Button Audit", desc: "Audit all links and buttons for navigation, href, and accessibility", category: "Links & Buttons", default: true },
  { id: "ada_compliance", label: "ADA / WCAG Compliance", desc: "Check for accessibility issues: alt text, ARIA labels, contrast, form labels", category: "Accessibility", default: true },
  { id: "ada_contrast", label: "Color Contrast Check", desc: "Verify text has sufficient contrast against backgrounds (WCAG AA)", category: "Accessibility", default: true },
];

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
  const [enabledTests, setEnabledTests] = useState<Set<string>>(
    () => new Set(TEST_CASES.filter(t => t.default).map(t => t.id))
  );

  const toggleTest = (id: string) => {
    setEnabledTests(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const testCategories = [...new Set(TEST_CASES.map(t => t.category))];

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
    mutationFn: ({ pages, testMode }: { pages: string; testMode: "design" | "ai" }) =>
      startRun(projectId, pages || undefined, testMode),
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
            { key: "test-cases", label: "Test Cases" },
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

      {/* Test Cases Tab */}
      {activeTab === "test-cases" && (
        <div className="max-w-2xl">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Test Configuration</h2>
            <p className="text-sm text-gray-500 mt-1">Select which tests to run when you start a QA run for this project.</p>
          </div>

          <div className="space-y-6">
            {testCategories.map(cat => (
              <div key={cat} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-5 py-3 bg-gray-50 border-b border-gray-100">
                  <h3 className="text-sm font-semibold text-gray-700">{cat}</h3>
                </div>
                <div className="divide-y divide-gray-50">
                  {TEST_CASES.filter(t => t.category === cat).map(test => (
                    <label
                      key={test.id}
                      className="flex items-start gap-4 px-5 py-4 hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <div className="pt-0.5">
                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                          enabledTests.has(test.id)
                            ? "bg-indigo-600 border-indigo-600"
                            : "border-gray-300"
                        }`}>
                          {enabledTests.has(test.id) && (
                            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                      </div>
                      <div className="flex-1" onClick={() => toggleTest(test.id)}>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-900">{test.label}</span>
                          {enabledTests.has(test.id) && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-medium">ON</span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">{test.desc}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={() => setEnabledTests(new Set(TEST_CASES.map(t => t.id)))}
              className="px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-300 rounded-lg hover:bg-indigo-50 transition-colors"
            >
              Enable All
            </button>
            <button
              onClick={() => setEnabledTests(new Set())}
              className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Disable All
            </button>
            <span className="text-xs text-gray-400 ml-2">
              {enabledTests.size} of {TEST_CASES.length} tests enabled
            </span>
          </div>
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
          onConfirm={(pages, testMode) => runMutation.mutate({ pages, testMode })}
          onCancel={() => setShowRunModal(false)}
          isLoading={runMutation.isPending}
        />
      )}
    </div>
  );
};

export default ProjectDetailPage;
