import type { ReactNode } from "react";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="spinner" role="status" aria-live="polite">
      <span className="spinner-ring" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function ErrorBanner({
  message,
  code,
  onDismiss,
}: {
  message: string;
  code?: string;
  onDismiss?: () => void;
}) {
  return (
    <div className="banner banner-error" role="alert">
      <div>
        {code ? <strong className="banner-code">{code.replaceAll("_", " ")}</strong> : null}
        <p>{message}</p>
      </div>
      {onDismiss ? (
        <button type="button" className="icon-button" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      ) : null}
    </div>
  );
}

export function NoticeBanner({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss?: () => void;
}) {
  return (
    <div className="banner banner-notice" role="status">
      <p>{message}</p>
      {onDismiss ? (
        <button type="button" className="icon-button" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-state-mark" aria-hidden="true">
        ◔
      </span>
      <h3>{title}</h3>
      {children ? <div className="empty-state-body">{children}</div> : null}
    </div>
  );
}
