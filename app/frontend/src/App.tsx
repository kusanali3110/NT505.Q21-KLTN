import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useState } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import Sidebar from './components/Layout/Sidebar';
import DashboardPage from './pages/DashboardPage';
import CamerasPage  from './pages/CamerasPage';
import AlertsPage   from './pages/AlertsPage';
import SettingsPage from './pages/SettingsPage';
import UsersPage    from './pages/UsersPage';
import LoginPage    from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import { useAuth }  from './hooks/useAuth';
import { useUnifiedEvents } from './hooks/useUnifiedEvents';
import { EventProvider } from './context/EventContext';

function PrivateApp() {
  const { user, logout } = useAuth();
  const [alertCount, setAlertCount] = useState(0);

  const location = useLocation();

  // Reset new alert count when navigating to /alerts
  if (location.pathname === '/alerts' && alertCount > 0) {
    setAlertCount(0);
  }

  // Real-time alert updates via Unified WebSocket
  useUnifiedEvents((evt) => {
    if (evt.type === 'alert') {
      if (location.pathname !== '/alerts') {
        setAlertCount(prev => prev + 1);
      }
      const label = evt.data.label ? evt.data.label.toUpperCase() : 'Event';
      toast.error(`New Alert: ${label} detected!`, { duration: 5000, icon: '⚠️' });
    } else if (evt.type === 'device_status') {
      if (evt.data.status === 'online') {
        toast.success(`Camera #${evt.data.device_id} is online`, { duration: 3000 });
      } else if (evt.data.status === 'offline') {
        toast.error(`Camera #${evt.data.device_id} went offline`, { duration: 3000, icon: '🔌' });
      }
    }
  });

  return (
    <div className="app-layout">
      <Sidebar user={user} alertCount={alertCount} onLogout={logout} />
      <div className="main-content">
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/cameras"   element={<CamerasPage />}  />
          <Route path="/alerts"    element={<AlertsPage />}   />
          <Route path="/settings"  element={<SettingsPage />} />
          {user?.role === 'admin' && (
            <Route path="/users" element={<UsersPage />} />
          )}
          <Route path="/"          element={<Navigate to="/dashboard" replace />} />
          <Route path="*"          element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </div>
    </div>
  );
}

function AuthGuard() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="spinner" />
      </div>
    );
  }

  return user ? (
    <EventProvider>
      <PrivateApp />
    </EventProvider>
  ) : <LoginPage />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="bottom-right"
        toastOptions={{
          duration: 5000,
          style: {
            background: 'var(--card-bg, #1a2332)',
            color: 'var(--text-primary, #e8eaf6)',
            border: '1px solid rgba(255,255,255,0.08)',
          },
        }}
      />
      <Routes>
        <Route path="/login"        element={<LoginPage />} />
        <Route path="/register"     element={<RegisterPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/*"            element={<AuthGuard />} />
      </Routes>
    </BrowserRouter>
  );
}
