import api from "./client";

export const startRun = (
  projectId: number,
  pages?: string,
  testMode: "design" | "ai" = "design"
) => {
  const params = new URLSearchParams();
  if (pages) params.set("pages", pages);
  if (testMode !== "design") params.set("test_mode", testMode);
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
