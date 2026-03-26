import api from "./client";

export const listIssues = (
  runId: number,
  params?: {
    severity?: string;
    type?: string;
    issue_page?: string;
    per_page?: number;
    page?: number;
  }
) => {
  const query = new URLSearchParams();
  if (params?.severity) query.set("severity", params.severity);
  if (params?.type) query.set("type", params.type);
  if (params?.issue_page) query.set("issue_page", params.issue_page);
  if (params?.per_page) query.set("per_page", String(params.per_page));
  if (params?.page) query.set("page", String(params.page));
  return api.get(`/api/runs/${runId}/issues?${query}`);
};

export const getIssue = (runId: number, issueId: number) =>
  api.get(`/api/runs/${runId}/issues/${issueId}`);
