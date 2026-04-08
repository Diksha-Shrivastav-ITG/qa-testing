import api from "./client";

export interface PageConfig {
  label: string;
  mode: "ai" | "design";
  shopifyUrl: string;
  referenceUrl?: string;
}

export const startRun = (
  projectId: number,
  pageConfigs?: PageConfig[],
  testMode?: "design" | "ai",
  testTypes?: string[],
  /** Legacy: comma-separated page paths for Full QA */
  pages?: string,
) => {
  // Customize tab: send JSON body with page_configs
  if (pageConfigs && pageConfigs.length > 0) {
    return api.post(`/api/projects/${projectId}/runs`, {
      page_configs: pageConfigs.map((pc) => ({
        label: pc.label,
        mode: pc.mode,
        shopify_url: pc.shopifyUrl,
        reference_url: pc.referenceUrl || null,
      })),
      test_types: testTypes,
    });
  }

  // Full QA tab: use query params (backward compatible)
  const params = new URLSearchParams();
  if (pages) params.set("pages", pages);
  if (testMode && testMode !== "ai") params.set("test_mode", testMode);
  if (testTypes && testTypes.length > 0) {
    testTypes.forEach((t) => params.append("test_types", t));
  }
  const qs = params.toString() ? `?${params.toString()}` : "";
  return api.post(`/api/projects/${projectId}/runs${qs}`);
};

export const listRuns = (projectId: number, page = 1) =>
  api.get(`/api/projects/${projectId}/runs?page=${page}`);

export const getRun = (runId: number) => api.get(`/api/runs/${runId}`);

export const cancelRun = (runId: number) =>
  api.post(`/api/runs/${runId}/cancel`);

export const getCaptures = (runId: number) =>
  api.get(`/api/runs/${runId}/captures`);

export const getAccessibility = (runId: number) =>
  api.get(`/api/runs/${runId}/accessibility`);

export const getLinkAudit = (runId: number) =>
  api.get(`/api/runs/${runId}/link-audit`);

export const getSeo = (runId: number) =>
  api.get(`/api/runs/${runId}/seo`);

export const getPerformance = (runId: number) =>
  api.get(`/api/runs/${runId}/performance`);

export const getComparisons = (runId: number) =>
  api.get(`/api/runs/${runId}/comparisons`);
