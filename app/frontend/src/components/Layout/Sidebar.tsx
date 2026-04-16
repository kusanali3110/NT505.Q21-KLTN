import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Camera, Bell, Settings, Shield, LogOut, Users, AlertTriangle
} from 'lucide-react';

interface SidebarProps {
  user?: { username: string; email: string; role?: string } | null;
  alertCount?: number;
  onLogout: () => void;
}

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/cameras',   icon: Camera,          label: 'Cameras'   },
  { to: '/alerts',    icon: Bell,            label: 'Alerts'    },
];



export default function Sidebar({ user, alertCount = 0, onLogout }: SidebarProps) {
  const [showConfirm, setShowConfirm] = useState(false);
  const isAdmin = user?.role === 'admin';

  return (
    <>
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <Shield size={18} color="white" />
          </div>
          <div className="sidebar-logo-text">
            <span>NT505.Q21-KLTN</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          <div className="sidebar-section-label">Main Menu</div>
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `sidebar-item${isActive ? ' active' : ''}`
              }
            >
              <Icon size={18} />
              {label}
              {label === 'Alerts' && alertCount > 0 && (
                <span className="badge">{alertCount > 99 ? '99+' : alertCount}</span>
              )}
            </NavLink>
          ))}

          {/* Admin-only */}
          {isAdmin && (
            <NavLink
              to="/users"
              className={({ isActive }) =>
                `sidebar-item${isActive ? ' active' : ''}`
              }
            >
              <Users size={18} />
              User
            </NavLink>
          )}

          {/* Settings */}
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `sidebar-item${isActive ? ' active' : ''}`
            }
          >
            <Settings size={18} />
            Settings
          </NavLink>
        </nav>

        {/* User footer */}
        <div className="sidebar-footer" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="sidebar-avatar" style={{ flexShrink: 0 }}>
            {user?.username?.charAt(0).toUpperCase() ?? 'U'}
          </div>
          <div className="sidebar-user-info" style={{ flex: 1, minWidth: 0, paddingRight: '8px' }}>
            <p style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.username ?? 'Admin'}</p>
            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block' }}>{user?.email ?? '—'}</span>
          </div>
          <button
            className="header-action-btn"
            onClick={() => setShowConfirm(true)}
            title="Logout"
            style={{ flexShrink: 0, marginLeft: 'auto', marginRight: '4px' }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* Logout Confirmation Modal Overlay */}
      {showConfirm && (
        <div className="modal-overlay" 
             style={{ 
               backgroundColor: 'rgba(0, 0, 0, 0.7)',
               backdropFilter: 'blur(4px)',
               zIndex: 9999 
             }} 
             onClick={() => setShowConfirm(false)}>
          <div className="modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 400, textAlign: 'center', padding: '32px' }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%', background: 'rgba(239, 68, 68, 0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px',
            }}>
              <AlertTriangle size={32} color="#ef4444" />
            </div>
            <h3 style={{ marginBottom: 12, fontSize: '1.5rem', fontWeight: 700 }}>Confirm Logout</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 28, fontSize: '1rem', lineHeight: 1.5 }}>
              Are you sure you want to end your session? You will be redirected to the login page.
            </p>
            <div style={{ display: 'flex', gap: 16 }}>
              <button
                className="btn-outline"
                onClick={() => setShowConfirm(false)}
                style={{ 
                  flex: 1, padding: '12px', borderRadius: '10px', 
                  border: '1px solid var(--border-color)', background: 'var(--bg-secondary)',
                  color: 'var(--text-main)', fontWeight: 600, fontSize: '0.95rem'
                }}
              >
                No, Stay
              </button>
              <button
                className="btn-primary"
                onClick={() => {
                  setShowConfirm(false);
                  onLogout();
                }}
                style={{ 
                  flex: 1, padding: '12px', borderRadius: '10px', 
                  background: '#ef4444', color: 'white', 
                  fontWeight: 600, fontSize: '0.95rem', border: 'none'
                }}
              >
                Yes, Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
