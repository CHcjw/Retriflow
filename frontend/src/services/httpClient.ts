import axios, { AxiosError } from "axios";

export const API_BASE_URL = import.meta.env.VITE_RETRIFLOW_API_BASE_URL ?? "";

const UNAUTHORIZED_EVENT = "retriflow:unauthorized";
let accessToken = "";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000
});

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      accessToken = "";
      dispatchUnauthorized();
    }
    return Promise.reject(error);
  }
);

export function setAccessToken(token: string) {
  accessToken = token.trim();
}

export function getAccessToken(): string {
  return accessToken;
}

export function getUnauthorizedEventName(): string {
  return UNAUTHORIZED_EVENT;
}

export function dispatchUnauthorized() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT));
  }
}

function toRequestError(error: unknown): Error {
  if (error instanceof AxiosError) {
    const message =
      typeof error.response?.data === "object" &&
      error.response?.data !== null &&
      "detail" in error.response.data &&
      typeof error.response.data.detail === "string"
        ? error.response.data.detail
        : error.message;
    return new Error(message);
  }

  return error instanceof Error ? error : new Error("Unknown request error");
}

export async function request<T>(config: {
  url: string;
  method?: "DELETE" | "GET" | "PATCH" | "POST" | "PUT";
  data?: FormData | Record<string, unknown>;
  headers?: Record<string, string>;
}): Promise<T> {
  try {
    const response = await apiClient.request<T>({
      url: config.url,
      method: config.method ?? "GET",
      data: config.data,
      headers: config.headers
    });
    return response.data;
  } catch (error) {
    throw toRequestError(error);
  }
}

export async function requestBlob(url: string): Promise<{ blob: Blob; filename: string }> {
  try {
    const response = await apiClient.request<Blob>({
      url,
      method: "GET",
      responseType: "blob"
    });
    const disposition = response.headers["content-disposition"];
    const filename = parseContentDispositionFilename(typeof disposition === "string" ? disposition : "") || "document-source";
    return { blob: response.data, filename };
  } catch (error) {
    throw toRequestError(error);
  }
}

export function parseContentDispositionFilename(disposition: string): string {
  const encodedMatch = /filename\*=UTF-8''([^;]+)/iu.exec(disposition);
  if (encodedMatch) {
    return decodeURIComponent(encodedMatch[1]);
  }
  const plainMatch = /filename="?([^";]+)"?/iu.exec(disposition);
  return plainMatch?.[1] ?? "";
}
