import { useState } from 'react';
import {
  User, Bell, Save, ChevronRight, LogOut
} from 'lucide-react';
import TopHeader from '../components/Layout/TopHeader';
import { useAuth } from '../hooks/useAuth';

type SettingsTab = 'profile' | 'notifications' | 'security' | 'system';

const TABS: { id: SettingsTab; icon: React.ReactNode; label: string }[] = [
  { id: 'profile',       icon: <User size={16} />,   label: 'Profile'        },
  { id: 'notifications', icon: <Bell size={16} />,   label: 'Notifications'  },
];

export default function SettingsPage() {
  const { logout } = useAuth();
  const [activeTab, setActiveTab] = useState<SettingsTab>('profile');
  const [saved, setSaved] = useState(false);

  // Mock form state
  const [profile, setProfile] = useState({ username: 'admin', email: 'admin@example.com', fullName: 'System Admin' });
  const [notifs,  setNotifs]  = useState({ email: true, motion: true, intrusion: true, fall: true, sound: false });

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
                onClick={logout}
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
                  <div className="form-group">
                    <label className="form-label">Username</label>
                    <input className="form-control" value={profile.username} onChange={e => setProfile(p => ({ ...p, username: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Full Name</label>
                    <input className="form-control" value={profile.fullName} onChange={e => setProfile(p => ({ ...p, fullName: e.target.value }))} />
                  </div>
                  <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                    <label className="form-label">Email Address</label>
                    <input className="form-control" type="email" value={profile.email} onChange={e => setProfile(p => ({ ...p, email: e.target.value }))} />
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
                  { key: 'email' as const,     label: 'Email Notifications', desc: 'Receive alerts via email' },
                  { key: 'motion' as const,    label: 'Motion Detected',     desc: 'Notify when motion is detected' },
                  { key: 'intrusion' as const, label: 'Intrusion Alert',     desc: 'Notify on intrusion events' },
                  { key: 'fall' as const,      label: 'Fall Detection',      desc: 'Notify on fall detection events' },
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
    </>
  );
}
