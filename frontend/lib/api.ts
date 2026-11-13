const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"
).replace(/\/$/, "");

const TOKEN_KEY = "civicops.session";

export class ApiError extends Error {
  status: number;
  code: string;
  errors?: unknown;

  constructor(message: string, status: number, code = "error", errors?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.errors = errors;
  }
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

function authHeaders(): Headers {
  const headers = new Headers();
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: Record<string, unknown> = {};
  try {
    payload = (await response.json()) as Record<string, unknown>;
  } catch {
    // The API may return an empty body for a gateway failure.
  }
  const detail =
    typeof payload.detail === "string"
      ? payload.detail
      : `Request failed with status ${response.status}.`;
  return new ApiError(
    detail,
    response.status,
    typeof payload.code === "string" ? payload.code : "error",
    payload.errors,
  );
}

type JsonBody = Record<string, unknown> | unknown[];

export type ApiRequestInit = Omit<RequestInit, "body"> & {
  body?: BodyInit | JsonBody | null;
};

function isBodyInit(value: NonNullable<ApiRequestInit["body"]>): value is BodyInit {
  return (
    typeof value === "string" ||
    value instanceof FormData ||
    value instanceof Blob ||
    value instanceof URLSearchParams ||
    value instanceof ArrayBuffer ||
    ArrayBuffer.isView(value) ||
    (typeof ReadableStream !== "undefined" && value instanceof ReadableStream)
  );
}

export async function apiFetch<T>(
  path: string,
  init: ApiRequestInit = {},
): Promise<T> {
  const headers = authHeaders();
  new Headers(init.headers).forEach((value, key) => headers.set(key, value));
  let body: ApiRequestInit["body"] = init.body ?? undefined;

  if (body && !isBodyInit(body)) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers,
      body,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Cannot reach the CivicOps API. Check that the backend is running.",
      0,
      "network_error",
    );
  }

  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiBlob(path: string): Promise<Blob> {
  const response = await fetch(apiUrl(path), {
    headers: authHeaders(),
    cache: "no-store",
  });
  if (!response.ok) throw await parseError(response);
  return response.blob();
}

export function buildQuery(
  values: Record<string, string | number | boolean | null | undefined | string[]>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) params.append(key, item);
    } else {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}
