import { useCallback, useEffect, useState } from "react";

import { ApiError, api, isAbortError } from "../api/client";
import type { ExplorerRequest, PageName } from "../api/types";
import { useSession } from "../context/session";

interface PageResult<T> {
  key: string;
  data: T | null;
  error: ApiError | null;
}

/**
 * Fetch a page payload whenever the resolved filter state changes.
 *
 * The request body is keyed by its JSON form, so an equal selection never
 * refetches while a real change does. Loading and errors are derived from the
 * key of the settled request, which keeps the effect free of synchronous state
 * updates.
 */
export function usePagePayload<T>(page: PageName, extra?: Record<string, unknown>) {
  const { sessionId, filterState } = useSession();
  const [result, setResult] = useState<PageResult<T> | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const bodyKey = JSON.stringify({ ...filterState, ...extra });
  const requestKey = `${bodyKey}#${reloadToken}`;

  useEffect(() => {
    if (!sessionId || !filterState) return;

    const controller = new AbortController();
    api
      .page<T>(
        sessionId,
        page,
        JSON.parse(bodyKey) as ExplorerRequest,
        controller.signal,
      )
      .then((data) => setResult({ key: requestKey, data, error: null }))
      .catch((caught: unknown) => {
        if (isAbortError(caught)) return;
        setResult({
          key: requestKey,
          data: null,
          error:
            caught instanceof ApiError
              ? caught
              : new ApiError(0, "UNEXPECTED_ERROR", "Could not load this page."),
        });
      });

    return () => controller.abort();
  }, [bodyKey, filterState, page, requestKey, sessionId]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return {
    data: result?.data ?? null,
    loading: result?.key !== requestKey,
    error: result?.key === requestKey ? result.error : null,
    reload,
  };
}
