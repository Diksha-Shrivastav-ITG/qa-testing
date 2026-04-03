import api from "./client";

export const startRun = (
  projectId: number,
  pages?: string,
  testMode: "design" | "ai" = "design",
  testTypes?: string[],
  pageReferenceUrls?: Record<string, string>
) => {
  const params = new URLSearchParams();
  if (pages) params.set("pages", pages);
  if (testMode !== "design") params.set("test_mode", testMode);
  if (testTypes && testTypes.length > 0) {
    testTypes.forEach((t) => params.append("test_types", t));
  }
  const qs = params.toString() ? `?${params.toString()}` : "";
  const body =
    pageReferenceUrls && Object.keys(pageReferenceUrls).length > 0
      ? { page_reference_urls: pageReferenceUrls }
      : undefined;
  return api.post(`/api/projects/${projectId}/runs${qs}`, body);
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
