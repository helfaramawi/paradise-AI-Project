import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import { ActiveDecisionProvider, AuthProvider, I18nProvider, ThemeProvider, useAuth } from "@/lib/app";
import { AppShell } from "@/components/AppShell";
import { Spinner } from "@/components/ui";
import Login from "@/pages/Login";

const CommandCenter = lazy(() => import("@/pages/CommandCenter"));
const Workspace = lazy(() => import("@/pages/Workspace"));
const IntakeWizard = lazy(() => import("@/pages/IntakeWizard"));
const ExecutionRoom = lazy(() => import("@/pages/ExecutionRoom"));
const AgentCourt = lazy(() => import("@/pages/AgentCourt"));
const ThreeFutures = lazy(() => import("@/pages/ThreeFutures"));
const TimeMachine = lazy(() => import("@/pages/TimeMachine"));
const SimulationLab = lazy(() => import("@/pages/SimulationLab"));
const FinancialImpact = lazy(() => import("@/pages/FinancialImpact"));
const RiskExplorer = lazy(() => import("@/pages/RiskExplorer"));
const ApprovalCenter = lazy(() => import("@/pages/ApprovalCenter"));
const History = lazy(() => import("@/pages/History"));
const Outcomes = lazy(() => import("@/pages/Outcomes"));
const DataConnections = lazy(() => import("@/pages/DataConnections"));
const Automation = lazy(() => import("@/pages/Automation"));
const Governance = lazy(() => import("@/pages/Governance"));
const Admin = lazy(() => import("@/pages/Admin"));

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 5000 } } });

function Protected() {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <Spinner />;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  return (
    <AppShell>
      <Suspense fallback={<Spinner />}>
        <Routes>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/decisions" element={<Workspace />} />
          <Route path="/decisions/new" element={<IntakeWizard />} />
          <Route path="/execution" element={<ExecutionRoom />} />
          <Route path="/execution/:runId" element={<ExecutionRoom />} />
          <Route path="/court" element={<AgentCourt />} />
          <Route path="/futures" element={<ThreeFutures />} />
          <Route path="/time-machine" element={<TimeMachine />} />
          <Route path="/lab" element={<SimulationLab />} />
          <Route path="/financial" element={<FinancialImpact />} />
          <Route path="/risk" element={<RiskExplorer />} />
          <Route path="/approvals" element={<ApprovalCenter />} />
          <Route path="/history" element={<History />} />
          <Route path="/outcomes" element={<Outcomes />} />
          <Route path="/data" element={<DataConnections />} />
          <Route path="/automation" element={<Automation />} />
          <Route path="/governance" element={<Governance />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <ThemeProvider>
        <I18nProvider>
          <AuthProvider>
            <ActiveDecisionProvider>
              <BrowserRouter>
                <Routes>
                  <Route path="/login" element={<Login />} />
                  <Route path="/*" element={<Protected />} />
                </Routes>
              </BrowserRouter>
            </ActiveDecisionProvider>
          </AuthProvider>
        </I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
