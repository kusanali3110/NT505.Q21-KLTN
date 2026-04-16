import { useState } from 'react';
import {
  User, Bell, Save, ChevronRight, LogOut, AlertTriangle
} from 'lucide-react';
import TopHeader from '../components/Layout/TopHeader';
import { useAuth } from '../hooks/useAuth';

type SettingsTab = 'profile' | 'notifications' | 'security' | 'system';

const TABS: { id: SettingsTab; icon: React.ReactNode; label: string }[] = [
  { id: 'profile',       icon: <User size={16} />,   label: 'Profile'        },
  { id: 'notifications', icon: <Bell size={16} />,   label: 'Notifications'  },
];

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');
  const [saved, setSaved] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  // Fallback state if user context is missing, otherwise synced with user
  const [profile, setProfile] = useState({ 
    username: user?.username || 'admin', 
    email: user?.email || 'admin@example.com',
    role: user?.role || 'user'
  });
  
  const [notifs,  setNotifs]  = useState({ alert: true, sound: false });

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <>
      <TopHeader title="Settings" subtitle="Manage your account and system preferences" />
      <div className="page-content">
        <div className="settings-grid">
          {/* Settings sidebar nav */}
          <div className="card" style={{ padding: 12 }}>
            {TABS.map(tab => (
              <button
                key={tab.id}
                className={`settings-nav-item${activeTab === tab.id ? ' active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
                style={{ width: '100%', justifyContent: 'space-between' }}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {tab.icon} {tab.label}
                </span>
                <ChevronRight size={14} style={{ opacity: 0.4 }} />
              </button>
            ))}
            
            <div style={{ marginTop: 24, borderTop: '1px solid var(--border-color)', paddingTop: 16 }}>
              <button
                className="settings-nav-item"
                style={{ width: '100%', justifyContent: 'space-between', color: 'var(--accent-red)' }}
                onClick={() => setShowLogoutConfirm(true)}
              >
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <LogOut size={16} /> Logout
                </span>
              </button>
            </div>
          </div>

          {/* Settings content */}
          <div>
            {/* Profile tab */}
            {activeTab === 'profile' && (
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Profile Settings</div>
                    <div className="card-subtitle">Update your account information</div>
                  </div>
                </div>

                {/* Avatar section removed. Render basic info layout */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                    <label className="form-label">Username</label>
                    <input className="form-control" value={profile.username} onChange={e => setProfile(p => ({ ...p, username: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Email Address <span style={{fontSize: '0.75rem', opacity: 0.6}}></span></label>
                    <input className="form-control" type="email" value={profile.email} disabled style={{opacity: 0.7, cursor: 'not-allowed'}} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Role <span style={{fontSize: '0.75rem', opacity: 0.6}}></span></label>
                    <input className="form-control" value={profile.role} disabled style={{opacity: 0.7, cursor: 'not-allowed', textTransform: 'capitalize'}} />
                  </div>
                </div>

                <div style={{ padding: '16px 0', borderTop: '1px solid var(--border-color)', marginTop: 24 }}>
                  <h4 style={{ marginBottom: 16 }}>Change Password</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                    <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                      <label className="form-label">Current Password</label>
                      <input className="form-control" type="password" placeholder="••••••••" />
                    </div>
                    <div className="form-group">
                      <label className="form-label">New Password</label>
                      <input className="form-control" type="password" placeholder="••••••••" />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Confirm New Password</label>
                      <input className="form-control" type="password" placeholder="••••••••" />
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
                  {saved && <span style={{ color: 'var(--accent-green)', fontSize: '0.85rem', alignSelf: 'center' }}>✓ Saved!</span>}
                  <button className="btn btn-primary" onClick={handleSave}>
                    <Save size={14} /> Save Changes
                  </button>
                </div>
              </div>
            )}

            {/* Notifications tab */}
            {activeTab === 'notifications' && (
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Notification Preferences</div>
                    <div className="card-subtitle">Control how you receive alerts</div>
                  </div>
                </div>
                {[
                  { key: 'alert' as const,     label: 'Turn on/off alerts',  desc: 'Receive system alerts and push notifications' },
                  { key: 'sound' as const,     label: 'Sound Alerts',        desc: 'Play audio on critical alerts' },
                ].map(item => (
                  <div key={item.key} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '14px 0', borderBottom: '1px solid var(--border-color)',
                  }}>
                    <div>
                      <p style={{ fontWeight: 500, marginBottom: 2 }}>{item.label}</p>
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{item.desc}</p>
                    </div>
                    <label style={{ position: 'relative', display: 'inline-block', width: 44, height: 24, flexShrink: 0 }}>
                      <input
                        type="checkbox"
                        checked={notifs[item.key]}
                        onChange={e => setNotifs(n => ({ ...n, [item.key]: e.target.checked }))}
                        style={{ opacity: 0, width: 0, height: 0 }}
                      />
                      <span style={{
                        position: 'absolute', cursor: 'pointer', inset: 0,
                        background: notifs[item.key] ? 'var(--accent-purple)' : 'var(--bg-card-hover)',
                        borderRadius: 24, transition: 'var(--transition-fast)',
                        border: '1px solid var(--border-color)',
                      }}>
                        <span style={{
                          position: 'absolute', top: 2, left: notifs[item.key] ? 21 : 2,
                          width: 18, height: 18, background: 'white', borderRadius: '50%',
                          transition: 'var(--transition-fast)', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                        }} />
                      </span>
                    </label>
                  </div>
                ))}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
                  {saved && <span style={{ color: 'var(--accent-green)', fontSize: '0.85rem', marginRight: 12, alignSelf: 'center' }}>✓ Saved!</span>}
                  <button className="btn btn-primary" onClick={handleSave}><Save size={14} /> Save</button>
                </div>
              </div>
            )}


          </div>
        </div>
      </div>

      {/* Logout Confirmation Modal Overlay */}
      {showLogoutConfirm && (
        <div className="modal-overlay" 
             style={{ 
               backgroundColor: 'rgba(0, 0, 0, 0.7)',
               backdropFilter: 'blur(4px)',
               zIndex: 9999 
             }} 
             onClick={() => setShowLogoutConfirm(false)}>
          <div className="modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: 400, textAlign: 'center', padding: '32px' }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%', background: 'rgba(239, 68, 68, 0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px'
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
                onClick={() => setShowLogoutConfirm(false)}
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
                  setShowLogoutConfirm(false);
                  logout();
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
