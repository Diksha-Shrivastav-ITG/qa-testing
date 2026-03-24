import api from "./client";

export const login = (email: string, password: string) =>
  api.post("/api/auth/login", { email, password });

export const signup = (email: string, name: string, password: string, role: string) =>
  api.post("/api/auth/signup", { email, name, password, role });

export const getMe = () => api.get("/api/users/me");
