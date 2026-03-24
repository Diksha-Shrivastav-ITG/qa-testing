import api from "./client";

export const listIssues = (
  runId: number,
  params?: { severity?: string; type?: string; page?: string }
) => {
  const query = new URLSearchParams();
  if (params?.severity) query.set("severity", params.severity);
  if (params?.type) query.set("type", params.type);
  if (params?.page) query.set("page", params.page);
  return api.get(`/api/runs/${runId}/issues?${query}`);
};

export const getIssue = (runId: number, issueId: number) =>
  api.get(`/api/runs/${runId}/issues/${issueId}`);
