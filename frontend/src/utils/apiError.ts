import { isAxiosError } from "axios";

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) return fallback;
  if (error.code === "ECONNABORTED" || error.code === "ETIMEDOUT") return "Сервер не ответил вовремя. Попробуйте ещё раз.";
  if (!error.response) return "Нет связи с сервером. Проверьте подключение и попробуйте ещё раз.";
  const detail = error.response.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}
