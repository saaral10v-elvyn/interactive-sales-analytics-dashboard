import type { ReactNode } from "react";
import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { useSession } from "./context/session";
import { HomePage } from "./pages/HomePage";
import { PreparePage } from "./pages/PreparePage";

const OverviewPage = lazy(() =>
  import("./pages/OverviewPage").then((module) => ({ default: module.OverviewPage })),
);
const ProductsPage = lazy(() =>
  import("./pages/ProductsPage").then((module) => ({ default: module.ProductsPage })),
);
const RegionsPage = lazy(() =>
  import("./pages/RegionsPage").then((module) => ({ default: module.RegionsPage })),
);
const ExplorerPage = lazy(() =>
  import("./pages/ExplorerPage").then((module) => ({ default: module.ExplorerPage })),
);

function RequireDataset({ children }: { children: ReactNode }) {
  const { session } = useSession();
  if (!session) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RequireCleaned({ children }: { children: ReactNode }) {
  const { session } = useSession();
  if (!session) return <Navigate to="/" replace />;
  if (!session.cleaned || session.cleaned.report.blocked) {
    return <Navigate to="/prepare" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route
          path="prepare"
          element={
            <RequireDataset>
              <PreparePage />
            </RequireDataset>
          }
        />
        <Route
          path="overview"
          element={
            <RequireCleaned>
              <OverviewPage />
            </RequireCleaned>
          }
        />
        <Route
          path="products"
          element={
            <RequireCleaned>
              <ProductsPage />
            </RequireCleaned>
          }
        />
        <Route
          path="regions"
          element={
            <RequireCleaned>
              <RegionsPage />
            </RequireCleaned>
          }
        />
        <Route
          path="explorer"
          element={
            <RequireCleaned>
              <ExplorerPage />
            </RequireCleaned>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
