// Thin fetch wrapper that attaches the current JWT (if any) and surfaces
// JSON errors in a consistent shape.

import { config } from "./config";
import { getAccessToken } from "./auth";

export class ApiError extends Error {
  status: number;
  correlationId?: string;
  constructor(status: number, message: string, correlationId?: string) {
    super(message);
    this.status = status;
    this.correlationId = correlationId;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  formData?: FormData;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.formData) {
    body = opts.formData;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(`${config.apiUrl}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body,
  });

  if (!res.ok) {
    let detail: { message?: string; correlation_id?: string } = {};
    try {
      detail = await res.json();
    } catch {
      // ignore — fall through with status text
    }
    throw new ApiError(
      res.status,
      detail.message || res.statusText,
      detail.correlation_id,
    );
  }

  // 204 / empty body
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
