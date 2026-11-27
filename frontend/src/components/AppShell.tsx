import { Suspense } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { formatNumber } from "../lib/format";
import { useSession } from "../context/session";
import { ErrorBanner, NoticeBanner, Spinner } from "./Feedback";
import { FilterBar } from "./FilterBar";
const NAV = [
  { to: "/overview", label: "Overview" },
  { to: "/products", label: "Products" },
  { to: "/regions", label: "Regions" },
  { to: "/explorer", label: "Explorer" },
];

const ANALYTICS_PATHS = new Set(NAV.map((item) => item.to));

export function AppShell() {
  const {
    session,
    booting,
    error,
    notice,
    filterState,
    reset,
    clearError,
    dismissNotice,
  } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const cleaned = session?.cleaned ?? null;
  const dashboardReady = Boolean(cleaned && !cleaned.report.blocked);
  const showFilters = dashboardReady && ANALYTICS_PATHS.has(location.pathname);
  const filterKey = JSON.stringify(filterState);

  async function handleReset() {
    if (!window.confirm("Start over and unload this dataset?")) return;
    await reset();
    navigate("/");
  }

  if (booting) {
    return (
      <div className="boot-screen">
        <Spinner label="Connecting to the analytics API" />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            SA
          </span>
          <span className="brand-text">
            <strong>Sales Analytics</strong>
            <small>Interactive dashboard</small>
          </span>
        </Link>

        <nav className="main-nav" aria-label="Dashboard pages">
          {dashboardReady
            ? NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    isActive ? "nav-link nav-link-active" : "nav-link"
                  }
                >
                  {item.label}
                </NavLink>
              ))
            : null}
        </nav>

        <div className="topbar-meta">
          {session ? (
            <>
              <div className="dataset-pill" title={session.dataset.filename}>
                <span>{session.dataset.filename}</span>
                <small>
                  {formatNumber(session.dataset.row_count)} rows
                  {cleaned ? ` · ${formatNumber(cleaned.rows)} cleaned` : ""}
                </small>
              </div>
              <button
                type="button"
                className="button button-ghost"
                onClick={() => void handleReset()}
              >
                New dataset
              </button>
            </>
          ) : null}
        </div>
      </header>

      {error ? (
        <div className="shell-banner">
          <ErrorBanner code={error.code} message={error.message} onDismiss={clearError} />
        </div>
      ) : null}
      {notice ? (
        <div className="shell-banner">
          <NoticeBanner message={notice} onDismiss={dismissNotice} />
        </div>
      ) : null}

      <main className="content">
        {showFilters ? (
          <div className="filter-slot">
            <FilterBar key={filterKey} />
          </div>
        ) : null}
        <Suspense fallback={<Spinner label="Loading page" />}>
          <Outlet />
        </Suspense>
      </main>

      <footer className="footer">
        <span>Built with FastAPI, React and a frozen analytics contract.</span>
        <span className="footer-muted">Amounts in INR · Demo data is generated, not real.</span>
      </footer>
    </div>
  );
}
