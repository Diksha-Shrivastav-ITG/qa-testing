import api from "./client";

export const downloadPdf = (runId: number) =>
  api.get(`/api/runs/${runId}/report/pdf`, { responseType: "blob" });

export const downloadHtml = (runId: number) =>
  api.get(`/api/runs/${runId}/report/html`, { responseType: "blob" });
