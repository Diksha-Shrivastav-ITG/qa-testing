import api from "./client";

export const startRun = (projectId: number) =>
  api.post(`/api/projects/${projectId}/runs`);

export const listRuns = (projectId: number, page = 1) =>
  api.get(`/api/projects/${projectId}/runs?page=${page}`);

export const getRun = (runId: number) => api.get(`/api/runs/${runId}`);

export const cancelRun = (runId: number) =>
  api.post(`/api/runs/${runId}/cancel`);
