import { createContext, useContext } from "react";

import type { ApiError } from "../api/client";
import type {
  CleaningResponse,
  DateFormatDecision,
  FilterRequest,
  FilterState,
  FiltersResponse,
  MetaResponse,
  SessionResponse,
} from "../api/types";

export interface SessionContextValue {
  sessionId: string | null;
  session: SessionResponse | null;
  meta: MetaResponse | null;
  booting: boolean;
  busy: boolean;
  error: ApiError | null;
  notice: string | null;
  filters: FiltersResponse | null;
  filterState: FilterState | null;
  filterSummary: string;
  startDemo: () => Promise<SessionResponse>;
  upload: (file: File) => Promise<SessionResponse>;
  updateMapping: (fields: Record<string, string | null>) => Promise<SessionResponse>;
  clean: (options: {
    date_format: DateFormatDecision;
    exclude_statuses: boolean;
  }) => Promise<CleaningResponse>;
  reset: () => Promise<void>;
  clearError: () => void;
  dismissNotice: () => void;
  applyFilters: (request: FilterRequest) => Promise<void>;
  resetFilters: () => Promise<void>;
  refreshFilters: () => Promise<void>;
}

export const SessionContext = createContext<SessionContextValue | null>(null);

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("useSession must be used inside a SessionProvider.");
  }
  return value;
}
