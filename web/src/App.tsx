import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api, ApiError } from "./api";
import UploadPage from "./pages/UploadPage";
import CoursesPage from "./pages/CoursesPage";
import DashboardPage from "./pages/DashboardPage";
import LessonPage from "./pages/LessonPage";
import BrandEditorPage from "./pages/BrandEditorPage";
import VoiceLibraryPage from "./pages/VoiceLibraryPage";
import DiagnosticsPage from "./pages/DiagnosticsPage";
import LoginPage from "./pages/LoginPage";

interface AuthStatus {
  authEnabled: boolean;
  authenticated: boolean;
}

const NAV_ITEMS = [
  { to: "/", label: "Upload", end: true },
  { to: "/courses", label: "Courses" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/brand", label: "Brand Editor" },
  { to: "/voices", label: "Voice Library" },
  { to: "/diagnostics", label: "Diagnostics" },
];

export default function App() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    refreshAuth();
  }, []);

  async function refreshAuth() {
    try {
      const status = await api.get<AuthStatus>("/auth/status");
      setAuth(status);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setAuth({ authEnabled: true, authenticated: false });
      }
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return <div className="app-loading">Loading Victory Video Studio…</div>;
  }

  if (auth && auth.authEnabled && !auth.authenticated) {
    return <LoginPage onLoggedIn={refreshAuth} />;
  }

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <div className="app-nav-brand">Victory Video Studio</div>
        <div className="app-nav-links">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => "app-nav-link" + (isActive ? " active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/courses/:courseId/lessons/:lessonId" element={<LessonPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/dashboard/:courseId" element={<DashboardPage />} />
          <Route path="/brand" element={<BrandEditorPage />} />
          <Route path="/voices" element={<VoiceLibraryPage />} />
          <Route path="/diagnostics" element={<DiagnosticsPage />} />
        </Routes>
      </main>
    </div>
  );
}
