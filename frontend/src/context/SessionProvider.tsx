import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { ApiError, api, isAbortError } from "../api/client";
import type {
  CleaningResponse,
  DateFormatDecision,
  FilterRequest,
  FilterState,
  FiltersResponse,
  MetaResponse,
  SessionResponse,
} from "../api/types";
import { formatNumber } from "../lib/format";
import { SessionContext } from "./session";

const STORAGE_KEY = "sales-dashboard.session-id";

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError(
    0,
    "UNEXPECTED_ERROR",
    error instanceof Error ? error.message : "Something went wrong.",
  );
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [booting, setBooting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [filters, setFilters] = useState<FiltersResponse | null>(null);
  const [filterState, setFilterState] = useState<FilterState | null>(null);
  const [filterSummary, setFilterSummary] = useState("");
  const noticeTimer = useRef<number | null>(null);

  const run = useCallback(async <T,>(action: () => Promise<T>): Promise<T> => {
    setBusy(true);
    setError(null);
    try {
      return await action();
    } catch (caught) {
      const apiError = toApiError(caught);
      setError(apiError);
      throw apiError;
    } finally {
      setBusy(false);
    }
  }, []);

  const remember = useCallback((result: SessionResponse) => {
    sessionStorage.setItem(STORAGE_KEY, result.session_id);
    setSessionId(result.session_id);
    setSession(result);
    setFilters(null);
    setFilterState(null);
    setFilterSummary("");
  }, []);

  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    const controller = new AbortController();
    let active = true;

    void (async () => {
      try {
        const [metaResult, sessionResult] = await Promise.all([
          api.meta(),
          stored ? api.getSession(stored, controller.signal) : Promise.resolve(null),
        ]);
        if (!active) return;
        setMeta(metaResult);
        if (sessionResult) {
          setSessionId(sessionResult.session_id);
          setSession(sessionResult);
        } else {
          sessionStorage.removeItem(STORAGE_KEY);
        }
      } catch (caught) {
        if (!active || isAbortError(caught)) return;
        if (caught instanceof ApiError && caught.status === 404) {
          sessionStorage.removeItem(STORAGE_KEY);
        } else {
          setError(toApiError(caught));
        }
      } finally {
        if (active) setBooting(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!sessionId || !session?.cleaned || session.cleaned.report.blocked) return;

    const controller = new AbortController();
    let active = true;
    void api
      .filters(sessionId, controller.signal)
      .then((result) => {
        if (!active) return;
        setFilters(result);
        setFilterState(result.state);
        setFilterSummary(result.summary);
      })
      .catch((caught: unknown) => {
        if (active && !isAbortError(caught)) setError(toApiError(caught));
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [sessionId, session?.cleaned]);

  useEffect(() => {
    if (!notice) return;
    if (noticeTimer.current !== null) window.clearTimeout(noticeTimer.current);
    noticeTimer.current = window.setTimeout(() => setNotice(null), 6000);
    return () => {
      if (noticeTimer.current !== null) window.clearTimeout(noticeTimer.current);
    };
  }, [notice]);

  const startDemo = useCallback(async () => {
    const result = await run(api.createDemo);
    remember(result);
    setNotice(
      `Demo dataset loaded — ${formatNumber(result.dataset.row_count)} rows ready.`,
    );
    return result;
  }, [remember, run]);

  const upload = useCallback(
    async (file: File) => {
      const result = await run(() => api.upload(file));
      remember(result);
      setNotice(
        `Loaded ${result.dataset.filename} — ${formatNumber(result.dataset.row_count)} rows ready.`,
      );
      return result;
    },
    [remember, run],
  );

  const updateMapping = useCallback(
    async (fields: Record<string, string | null>) => {
      if (!sessionId) {
        throw new ApiError(409, "NO_SESSION", "Load a dataset first.");
      }
      const result = await run(() => api.updateMapping(sessionId, fields));
      remember(result);
      setNotice("Column mapping saved. Clean the dataset to continue.");
      return result;
    },
    [remember, run, sessionId],
  );

  const clean = useCallback(
    async (options: {
      date_format: DateFormatDecision;
      exclude_statuses: boolean;
    }): Promise<CleaningResponse> => {
      if (!sessionId) {
        throw new ApiError(409, "NO_SESSION", "Load a dataset first.");
      }
      const result = await run(() => api.clean(sessionId, options));
      setSession((previous) =>
        previous
          ? { ...previous, cleaned: result.cleaned, revision: result.revision }
          : previous,
      );
      setNotice("Dataset cleaned. The dashboard is ready.");
      return result;
    },
    [run, sessionId],
  );

  const reset = useCallback(async () => {
    if (sessionId) {
      try {
        await api.deleteSession(sessionId);
      } catch {
        // The session may already have expired; clearing locally is enough.
      }
    }
    sessionStorage.removeItem(STORAGE_KEY);
    setSessionId(null);
    setSession(null);
    setFilters(null);
    setFilterState(null);
    setFilterSummary("");
    setError(null);
    setNotice(null);
  }, [sessionId]);

  const applyFilters = useCallback(
    async (request: FilterRequest) => {
      if (!sessionId) return;
      const resolved = await run(() => api.resolveFilters(sessionId, request));
      setFilterState(resolved.state);
      setFilterSummary(resolved.summary);
    },
    [run, sessionId],
  );

  const resetFilters = useCallback(async () => {
    const preset = meta?.filters.default_preset ?? "last_90_days";
    await applyFilters({ preset });
  }, [applyFilters, meta?.filters.default_preset]);

  const refreshFilters = useCallback(async () => {
    if (!sessionId) return;
    const result = await run(() => api.filters(sessionId));
    setFilters(result);
    setFilterState(result.state);
    setFilterSummary(result.summary);
  }, [run, sessionId]);

  const value = useMemo(
    () => ({
      sessionId,
      session,
      meta,
      booting,
      busy,
      error,
      notice,
      filters,
      filterState,
      filterSummary,
      startDemo,
      upload,
      updateMapping,
      clean,
      reset,
      clearError: () => setError(null),
      dismissNotice: () => setNotice(null),
      applyFilters,
      resetFilters,
      refreshFilters,
    }),
    [
      applyFilters,
      booting,
      busy,
      clean,
      error,
      filterState,
      filterSummary,
      filters,
      meta,
      notice,
      refreshFilters,
      reset,
      resetFilters,
      session,
      sessionId,
      startDemo,
      updateMapping,
      upload,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
