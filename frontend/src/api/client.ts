import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
});

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});
