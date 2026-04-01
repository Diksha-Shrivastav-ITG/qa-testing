import api from "./client";

export const listProjects = (page = 1, perPage = 20) =>
  api.get(`/api/projects?page=${page}&per_page=${perPage}`);

export const getProject = (id: number) => api.get(`/api/projects/${id}`);

export const createProject = (data: {
  name: string;
  shopify_url: string;
  source_type: string;
  source_url?: string;
  shopify_password?: string;
  figma_token?: string;
  page_mappings?: Record<string, string>;
}) => api.post("/api/projects", data);

export const updateProject = (id: number, data: Record<string, unknown>) =>
  api.put(`/api/projects/${id}`, data);

export const deleteProject = (id: number) => api.delete(`/api/projects/${id}`);
