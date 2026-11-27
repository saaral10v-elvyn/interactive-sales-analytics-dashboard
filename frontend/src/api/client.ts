/**
 * Typed client for the FastAPI analytics API.
 *
 * The client never computes business rules. It forwards a filter selection and
 * renders whatever payload comes back, which keeps the Python domain layer
 * authoritative.
 */

import type {
  ApiErrorBody,
  CleaningResponse,
  DateInspectionResponse,
  DateFormatDecision,
  ExplorerPayload,
  ExplorerRequest,
  ExportKind,
  FilterRequest,
  FiltersResponse,
  MetaResponse,
  OverviewPayload,
  PageName,
  ProductsPayload,
  RegionsPayload,
  ResolvedFilters,
  SessionResponse,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body?.error?.code) {
      return new ApiError(
        response.status,
        body.error.code,
        body.error.message,
        body.error.details,
      );
    }
  } catch {
    // Fall through to a generic error when the body is not the envelope.
  }
  return new ApiError(
    response.status,
    "HTTP_ERROR",
    `The server answered with status ${response.status}.`,
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "Cannot reach the API. Start the backend and try again.",
    );
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function jsonRequest(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

function pagePath(sessionId: string, page: PageName): string {
  return `/api/datasets/${sessionId}/${page}`;
}

async function download(
  sessionId: string,
  kind: ExportKind,
  body?: FilterRequest & { search?: string },
): Promise<{ blob: Blob; filename: string }> {
  const path = `/api/datasets/${sessionId}/exports/${kind}`;
  const init: RequestInit =
    kind === "filtered" ? jsonRequest("POST", body ?? {}) : { method: "GET" };
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError(0, "NETWORK_ERROR", "Cannot reach the API.");
  }
  if (!response.ok) throw await parseError(response);

  const header = response.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(header);
  return {
    blob: await response.blob(),
    filename: match?.[1]?.trim() ?? `sales_${kind}.csv`,
  };
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  meta: () => request<MetaResponse>("/api/meta"),

  createDemo: () =>
    request<SessionResponse>("/api/datasets/demo", { method: "POST" }),

  upload: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<SessionResponse>("/api/datasets", {
      method: "POST",
      body: data,
    });
  },

  getSession: (sessionId: string, signal?: AbortSignal) =>
    request<SessionResponse>(`/api/datasets/${sessionId}`, { signal }),

  deleteSession: (sessionId: string) =>
    request<void>(`/api/datasets/${sessionId}`, { method: "DELETE" }),

  updateMapping: (sessionId: string, fields: Record<string, string | null>) =>
    request<SessionResponse>(
      `/api/datasets/${sessionId}/mapping`,
      jsonRequest("PUT", { fields }),
    ),

  dateInspection: (sessionId: string, signal?: AbortSignal) =>
    request<DateInspectionResponse>(
      `/api/datasets/${sessionId}/date-inspection`,
      { signal },
    ),

  clean: (
    sessionId: string,
    options: { date_format: DateFormatDecision; exclude_statuses: boolean },
  ) =>
    request<CleaningResponse>(
      `/api/datasets/${sessionId}/cleaning`,
      jsonRequest("POST", options),
    ),

  filters: (sessionId: string, signal?: AbortSignal) =>
    request<FiltersResponse>(`/api/datasets/${sessionId}/filters`, { signal }),

  resolveFilters: (sessionId: string, selection: FilterRequest) =>
    request<ResolvedFilters>(
      `/api/datasets/${sessionId}/filters/resolve`,
      jsonRequest("POST", selection),
    ),

  page: <T>(
    sessionId: string,
    page: PageName,
    body?: ExplorerRequest,
    signal?: AbortSignal,
  ) => request<T>(pagePath(sessionId, page), { ...jsonRequest("POST", body ?? {}), signal }),

  overview: (sessionId: string, body?: FilterRequest, signal?: AbortSignal) =>
    api.page<OverviewPayload>(sessionId, "overview", body, signal),

  products: (sessionId: string, body?: FilterRequest, signal?: AbortSignal) =>
    api.page<ProductsPayload>(sessionId, "products", body, signal),

  regions: (sessionId: string, body?: FilterRequest, signal?: AbortSignal) =>
    api.page<RegionsPayload>(sessionId, "regions", body, signal),

  explorer: (sessionId: string, body?: ExplorerRequest, signal?: AbortSignal) =>
    api.page<ExplorerPayload>(sessionId, "explorer", body, signal),

  download,
};
