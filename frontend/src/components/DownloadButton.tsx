import { useState } from "react";

import { api, saveBlob } from "../api/client";
import type { ExportKind, FilterRequest } from "../api/types";
import { useSession } from "../context/session";

export function DownloadButton({
  kind,
  label,
  body,
  disabled = false,
  variant = "secondary",
}: {
  kind: ExportKind;
  label: string;
  body?: FilterRequest & { search?: string };
  disabled?: boolean;
  variant?: "primary" | "secondary";
}) {
  const { sessionId } = useSession();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const { blob, filename } = await api.download(sessionId, kind, body);
      saveBlob(blob, filename);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Download failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="download">
      <button
        type="button"
        className={variant === "primary" ? "button button-primary" : "button button-secondary"}
        onClick={() => void handleDownload()}
        disabled={disabled || loading}
      >
        <span aria-hidden="true">↓</span> {loading ? "Preparing…" : label}
      </button>
      {error ? <span className="download-error">{error}</span> : null}
    </div>
  );
}
