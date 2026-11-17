import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import { useAuth } from "./lib/auth";
import { Login, Onboarding } from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import { ProjectNew, Projects } from "./pages/Projects";
import ProjectDetail from "./pages/ProjectDetail";
import DocumentView from "./pages/DocumentView";
import EventDetail from "./pages/EventDetail";
import EntitlementDetail from "./pages/EntitlementDetail";
import Valuation from "./pages/Valuation";
import ClaimDetail from "./pages/ClaimDetail";
import DeadlineCalendar from "./pages/DeadlineCalendar";
import Reports from "./pages/Reports";
import { Platform, OrgSettings, Subscription, UsersAdmin } from "./pages/Admin";

export default function App() {
  const { me, loading, can } = useAuth();
  if (loading) return <Spinner />;
  if (!me) {
    return (
      <Routes>
        <Route path="/register" element={<Onboarding />} />
        <Route path="*" element={<Login />} />
      </Routes>
    );
  }
  if (!me.organization.onboarding_completed && me.role === "admin") {
    return <Routes><Route path="*" element={<Onboarding />} /></Routes>;
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={can("dashboard.executive") ? <Dashboard /> : <Navigate to="/projects" replace />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/new" element={<ProjectNew />} />
        <Route path="projects/:id" element={<ProjectDetail />} />
        <Route path="projects/:id/:tab" element={<ProjectDetail />} />
        <Route path="documents/:id" element={<DocumentView />} />
        <Route path="events/:id" element={<EventDetail />} />
        <Route path="entitlements/:id" element={<EntitlementDetail />} />
        <Route path="entitlements/:id/valuation" element={<Valuation />} />
        <Route path="claims/:id" element={<ClaimDetail />} />
        <Route path="deadlines" element={<DeadlineCalendar />} />
        <Route path="reports" element={<Reports />} />
        <Route path="admin/users" element={<UsersAdmin />} />
        <Route path="admin/settings" element={<OrgSettings />} />
        <Route path="admin/subscription" element={<Subscription />} />
        <Route path="platform" element={<Platform />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
