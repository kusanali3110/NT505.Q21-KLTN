import { useEffect, useMemo, useState } from 'react';
import {
  Plus, Search,
  Pencil, Trash2, Wifi, WifiOff, AlertTriangle, Camera
} from 'lucide-react';
import TopHeader from '../components/Layout/TopHeader';

import { deviceApi, type Device, type DeviceProvisioning } from '../services/api';
import { useUnifiedEvents } from '../hooks/useUnifiedEvents';

export default function CamerasPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);

  // Real-time status updates
  useUnifiedEvents((evt) => {
    if (evt.type === 'device_status') {
      setDevices(prev => prev.map(d => 
        d.id === evt.data.device_id ? { 
          ...d, 
          status: evt.data.status as 'online' | 'offline',
          provisioning_status: evt.data.provisioning_status ?? d.provisioning_status
        } : d
      ));
    }
  });

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'all' | 'online' | 'offline' | 'warning'>('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<number | null>(null);

  // Add/Edit form state
  const [form, setForm] = useState({ name: '', location: '', notes: '' });
  const [editId, setEditId] = useState<number | null>(null);
  const [formError, setFormError] = useState('');
  const [provisioning, setProvisioning] = useState<DeviceProvisioning | null>(null);
  const [now, setNow] = useState(Date.now());
  const [copied, setCopied] = useState(false);

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const d = await deviceApi.list();
      setDevices(d);
    } catch {
      setDevices([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDevices(); }, []);
  useEffect(() => {
    if (!provisioning) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [provisioning]);

  const provisioningCountdown = useMemo(() => {
    if (!provisioning?.onboarding_expires_at) return null;
    const end = new Date(provisioning.onboarding_expires_at).getTime();
    const diff = Math.max(0, end - now);
    const mins = Math.floor(diff / 60000);
    const secs = Math.floor((diff % 60000) / 1000);
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }, [provisioning, now]);

  const filtered = devices.filter(d => {
    const matchSearch = d.name.toLowerCase().includes(search.toLowerCase()) ||
      (d.location ?? '').toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'all' || d.status === filter;
    return matchSearch && matchFilter;
  });

  const getDeviceUiStatus = (d: Device) => {
    const provisioning = d.provisioning_status ?? 'pending';
    if (provisioning !== 'active') {
      const label = provisioning === 'pending' ? 'Waiting for verification' : provisioning === 'expired' ? 'Expired' : provisioning;
      return {
        label,
        badgeVariant: 'warning' as const,
        icon: <AlertTriangle size={18} color="var(--accent-yellow)" />,
      };
    }

    if (d.status === 'online') {
      return {
        label: 'Online',
        badgeVariant: 'success' as const,
        icon: <Wifi size={18} color="var(--accent-green)" />,
      };
    }

    if (d.status === 'offline') {
      return {
        label: 'Offline',
        badgeVariant: 'danger' as const,
        icon: <WifiOff size={18} color="var(--accent-red)" />,
      };
    }

    return {
      label: 'Warning',
      badgeVariant: 'warning' as const,
      icon: <AlertTriangle size={18} color="var(--accent-yellow)" />,
    };
  };

  const openEdit = (device: Device) => {
    setEditId(device.id);
    setForm({ name: device.name, location: device.location ?? '', notes: device.notes ?? '' });
    setShowAddModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    try {
      if (editId) {
        const updated = await deviceApi.update(editId, form);
        setDevices(ds => ds.map(d => d.id === editId ? updated : d));
      } else {
        const created = await deviceApi.create({ name: form.name, location: form.location, notes: form.notes });
        setProvisioning(created);
        await fetchDevices();
      }
      setShowAddModal(false);
      setEditId(null);
      setForm({ name: '', location: '', notes: '' });
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Error saving camera');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deviceApi.delete(id);
      setDevices(ds => ds.filter(d => d.id !== id));
    } catch {/* silently fail */}
    setShowDeleteConfirm(null);
  };

  return (
    <>
      <TopHeader
        title="Cameras"
        subtitle={`${devices.length} cameras registered`}
        onRefresh={fetchDevices}
      />
      <div className="page-content">
        {/* Filter bar */}
        <div className="filter-bar" style={{ justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {(['all', 'online', 'offline', 'warning'] as const).map(f => (
              <button
                key={f}
                className={`filter-tab${filter === f ? ' active' : ''}`}
                onClick={() => setFilter(f)}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
                {f !== 'all' && (
                  <span style={{ marginLeft: 4, opacity: 0.7 }}>
                    ({devices.filter(d => d.status === f).length})
                  </span>
                )}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {/* Search */}
            <div className="header-search" style={{ maxWidth: 220 }}>
              <Search size={15} color="var(--text-muted)" />
              <input
                type="text"
                placeholder="Search cameras…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            {/* No view toggle: always render table (list) */}
            <button className="btn btn-primary btn-sm" onClick={() => { setEditId(null); setForm({ name: '', location: '', notes: '' }); setShowAddModal(true); }}>
              <Plus size={16} /> Add Camera
            </button>
          </div>
        </div>

        {/* Cameras table (list view) */}
        {loading ? (
          <div className="spinner" />
        ) : filtered.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: 48 }}>
            <Camera size={48} style={{ opacity: 0.2, marginBottom: 12 }} />
            <p style={{ color: 'var(--text-secondary)' }}>No cameras found</p>
          </div>
        ) : (
          <div className="card">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Name</th>
                  <th>Location</th>
                  <th>Notes</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(device => (
                  <tr key={device.id}>
                    <td><span className="table-id">#{device.id}</span></td>
                    <td style={{ fontWeight: 600 }}>{device.name}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{device.location ?? '—'}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{device.notes ?? '—'}</td>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {getDeviceUiStatus(device).icon}
                        <span className={`badge badge-${getDeviceUiStatus(device).badgeVariant}`}>
                          {getDeviceUiStatus(device).label}
                        </span>
                      </span>
                    </td>
                    <td onClick={e => e.stopPropagation()}>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button className="btn btn-secondary btn-sm" onClick={() => openEdit(device)}>
                          <Pencil size={12} /> Edit
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={() => setShowDeleteConfirm(device.id)}>
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Add / Edit modal ── */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">{editId ? 'Edit Camera' : 'Add Camera'}</div>
              <button className="modal-close" onClick={() => setShowAddModal(false)}>✕</button>
            </div>
            <form onSubmit={handleSubmit}>
              {formError && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: 10, marginBottom: 16, color: 'var(--accent-red)', fontSize: '0.85rem' }}>
                  {formError}
                </div>
              )}
              <div className="form-group">
                <label className="form-label">Camera Name*</label>
                <input className="form-control" required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Front Door Cam" />
              </div>
              <div className="form-group">
                <label className="form-label">Location</label>
                <input className="form-control" value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} placeholder="e.g. Building A - Floor 1" />
              </div>
              <div className="form-group">
                <label className="form-label">Notes</label>
                <input className="form-control" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="e.g. Entrance camera, fixed mount" />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowAddModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">{editId ? 'Save Changes' : 'Add Camera'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Delete confirm modal ── */}
      {showDeleteConfirm !== null && (
        <div className="modal-overlay" onClick={() => setShowDeleteConfirm(null)}>
          <div className="modal" style={{ maxWidth: 400 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title" style={{ color: 'var(--accent-red)' }}>Delete Camera</div>
              <button className="modal-close" onClick={() => setShowDeleteConfirm(null)}>✕</button>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 8 }}>
              Are you sure you want to remove this camera? This action cannot be undone.
            </p>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowDeleteConfirm(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={() => handleDelete(showDeleteConfirm)}>
                <Trash2 size={14} /> Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Provisioning token modal ── */}
      {provisioning && (
        <div className="modal-overlay" onClick={() => setProvisioning(null)}>
          <div className="modal" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">Device Provisioning Token</div>
              <button className="modal-close" onClick={() => setProvisioning(null)}>✕</button>
            </div>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 12 }}>
              Copy this token into the <strong>DEVICE_TOKEN</strong> field in the <i>.env</i> file of your edge-agent. 
              <br/>This onboarding token expires in <strong>{provisioningCountdown ?? '00:00'}</strong>.
            </p>
            <div className="form-group">
              <label className="form-label">Onboarding Token (shown once)</label>
              <input className="form-control" readOnly value={provisioning.onboarding_token} />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                className="btn btn-secondary"
                onClick={async () => {
                  await navigator.clipboard.writeText(provisioning.onboarding_token);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
              >
                {copied ? 'Copied!' : 'Copy Token'}
              </button>
              <button className="btn btn-primary" onClick={() => setProvisioning(null)}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
