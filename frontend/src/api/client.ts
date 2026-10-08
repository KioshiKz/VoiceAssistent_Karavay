import axios from "axios";
import type { InternalAxiosRequestConfig } from "axios";
import type { TokenResponse } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  timeout: 15000,
});

let accessToken: string | null = null;
let sessionVersion = 0;
let refreshing: Promise<TokenResponse> | null = null;
const sessionClient = axios.create({ baseURL: BASE_URL, withCredentials: true, timeout: 15000 });

export function setAccessToken(token: string | null) {
  accessToken = token;
  sessionVersion += 1;
}

export function refreshSession(): Promise<TokenResponse> {
  if (refreshing) return refreshing;
  const version = sessionVersion;
  const request = sessionClient.post<TokenResponse>("/auth/refresh").then(({ data }) => {
    if (version !== sessionVersion) throw new Error("Session changed during refresh");
    accessToken = data.access_token;
    return data;
  }).catch((error: unknown) => {
    if (version === sessionVersion && axios.isAxiosError(error) && error.response?.status === 401) {
      setAccessToken(null);
      window.dispatchEvent(new Event("auth-session-expired"));
    }
    throw error;
  }).finally(() => {
    if (refreshing === request) refreshing = null;
  });
  refreshing = request;
  return request;
}

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use((response) => response, async (error: unknown) => {
  if (!axios.isAxiosError(error)) throw error;
  const config = error.config as (InternalAxiosRequestConfig & { sessionRetried?: boolean }) | undefined;
  if (error.response?.status !== 401 || !config || config.sessionRetried || /\/auth\/(login|logout|refresh)/.test(config.url ?? "")) {
    throw error;
  }
  config.sessionRetried = true;
  // Requests that failed together can reuse the token already refreshed by another request.
  if (!accessToken || config.headers.Authorization === `Bearer ${accessToken}`) await refreshSession();
  config.headers.Authorization = `Bearer ${accessToken}`;
  return apiClient.request(config);
});
