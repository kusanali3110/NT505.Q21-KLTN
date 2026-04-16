import { useEffect, useState } from 'react';
import {
  AlertTriangle, Activity, ShieldAlert, CheckCircle2,
  Filter, Calendar, Search, Trash2, MoreVertical, Eye, EyeOff, CheckSquare, PlayCircle, X
} from 'lucide-react';
import toast from 'react-hot-toast';
import { formatDistanceToNow, format } from 'date-fns';
import TopHeader from '../components/Layout/TopHeader';
import { alertApi, type Alert, API_BASE } from '../services/api';
import { useUnifiedEvents } from '../hooks/useUnifiedEvents';

const SEVERITY_CONFIG = {
  low:      { cls: 'badge-info',    icon: <Activity size={15} />,    bg: 'rgba(59,130,246,0.12)' },
  medium:   { cls: 'badge-warning', icon: <AlertTriangle size={15} />, bg: 'rgba(245,158,11,0.12)' },
  high:     { cls: 'badge-danger',  icon: <ShieldAlert size={15} />,   bg: 'rgba(239,68,68,0.12)' },
  critical: { cls: 'badge-danger',  icon: <ShieldAlert size={15} />,   bg: 'rgba(239,68,68,0.2)'  },
};

export default function AlertsPage() {
  const [alerts, setAlerts]   = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch]   = useState('');
  const [severityFilter, setSeverityFilter] = useState<'all'|'low'|'medium'|'high'|'critical'>('all');
  const [statusFilter,   setStatusFilter]   = useState<'all'|'unread'|'read'>('all');
  const [openDropdown, setOpenDropdown] = useState<number | null>(null);
  const [playingVideo, setPlayingVideo] = useState<string | null>(null);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const data = await alertApi.list();
      setAlerts(data);
    } catch { setAlerts([]); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAlerts(); }, []);

  useUnifiedEvents((event) => {
    if (event.type === 'alert' && event.data) {
      const d = event.data;
      if (d.occurred_at) {
        // New alert incoming from MQTT
        const newAlert: Alert = {
          id: d.id,
          device_id: d.device_id,
          type: d.label?.toLowerCase() || 'unknown',
          severity: (d.confidence > 0.8 ? 'critical' : (d.confidence > 0.5 ? 'high' : 'medium')) as Alert['severity'],
          message: `Detected ${d.label} with ${(d.confidence * 100).toFixed(0)}% confidence`,
          timestamp: d.occurred_at,
          resolved: d.acknowledged || false,
          videoUrl: d.video_url ? (d.video_url.startsWith('http') ? d.video_url : `${API_BASE}${d.video_url}`) : undefined,
        };
        setAlerts(prev => {
          if (prev.some(a => a.id === d.id)) return prev;
          return [newAlert, ...prev];
        });
      } else if (d.video_url) {
        // Video upload completed for a recent alert
        setAlerts(prev => prev.map(a => 
          a.id === d.id ? { ...a, videoUrl: d.video_url.startsWith('http') ? d.video_url : `${API_BASE}${d.video_url}` } : a
        ));
      }
    }
  });

  const handleUpdateStatus = async (id: number, read: boolean) => {
    try {
      await alertApi.updateStatus(id, read);
      setAlerts(prev => prev.map(a => a.id === id ? { ...a, resolved: read } : a));
      toast.success(`Marked as ${read ? 'read' : 'unread'}`);
    } catch { toast.error('Failed to update alert'); }
    setOpenDropdown(null);
  };

  const handleAcknowledgeAll = async () => {
    try {
      await alertApi.acknowledgeAll();
      setAlerts(prev => prev.map(a => ({ ...a, resolved: true })));
      toast.success('All alerts marked as read');
    } catch { toast.error('Failed to update alerts'); }
  };

  const handleDelete = async (id: number) => {
    try {
      await alertApi.delete(id);
      setAlerts(prev => prev.filter(a => a.id !== id));
      toast.success('Alert deleted');
    } catch { toast.error('Failed to delete alert'); }
    setOpenDropdown(null);
  };

  const filtered = alerts.filter(a => {
    const matchSeverity = severityFilter === 'all' || a.severity === severityFilter;
    const matchStatus   = statusFilter === 'all' ||
      (statusFilter === 'unread' && !a.resolved) ||
      (statusFilter === 'read' && a.resolved);
    const matchSearch   = a.message.toLowerCase().includes(search.toLowerCase()) ||
      (a.device_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
      a.type.toLowerCase().includes(search.toLowerCase());
    return matchSeverity && matchStatus && matchSearch;
  });

  const activeCount = alerts.filter(a => !a.resolved).length;

  return (
    <>
      <TopHeader
        title="Alerts"
        subtitle={`${activeCount} unread alert${activeCount !== 1 ? 's' : ''}`}
        alertCount={activeCount}
        onRefresh={fetchAlerts}
      />
      <div className="page-content">
        {/* Filter bar */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            {/* Search */}
            <div className="header-search" style={{ flex: 1, maxWidth: 320 }}>
              <Search size={15} color="var(--text-muted)" />
              <input
                type="text"
                placeholder="Search alerts…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>

            {/* Severity */}
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <Filter size={14} color="var(--text-muted)" />
              {(['all', 'low', 'medium', 'high', 'critical'] as const).map(s => (
                <button
                  key={s}
                  className={`filter-tab${severityFilter === s ? ' active' : ''}`}
                  onClick={() => setSeverityFilter(s)}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>

            {/* Status */}
            <div style={{ display: 'flex', gap: 6 }}>
              {(['all', 'unread', 'read'] as const).map(s => (
                <button
                  key={s}
                  className={`filter-tab${statusFilter === s ? ' active' : ''}`}
                  onClick={() => setStatusFilter(s)}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Summary cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
          {[
            { label: 'Total', count: alerts.length, color: 'var(--accent-purple)' },
            { label: 'Unread', count: alerts.filter(a => !a.resolved).length, color: 'var(--accent-red)' },
            { label: 'Read', count: alerts.filter(a => a.resolved).length, color: 'var(--accent-green)' },
            { label: 'Critical', count: alerts.filter(a => a.severity === 'critical').length, color: 'var(--accent-yellow)' },
          ].map(s => (
            <div key={s.label} className="card" style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{s.label}</span>
              <span style={{ fontSize: '1.4rem', fontWeight: 700, color: s.color }}>{s.count}</span>
            </div>
          ))}
        </div>

        {/* Alerts list */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Alert Log</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Calendar size={14} color="var(--text-muted)" />
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  {filtered.length} events
                </span>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={handleAcknowledgeAll}>
                <CheckSquare size={14} /> Mark All Read
              </button>
            </div>
          </div>

          {loading ? (
            <div className="spinner" />
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-muted)' }}>
              <CheckCircle2 size={40} style={{ opacity: 0.3, marginBottom: 8 }} />
              <p>No alerts match your filters</p>
            </div>
          ) : (
            <div style={{ overflowX: 'visible', paddingBottom: '140px' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#ID</th>
                    <th>Severity</th>
                    <th>Media</th>
                    <th>Type</th>
                    <th>Camera</th>
                    <th>Message</th>
                    <th>Time</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(alert => {
                    const cfg = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.low;
                    return (
                      <tr key={alert.id} className={!alert.resolved ? 'unread-row' : ''}>
                        <td><span className="table-id">#{alert.id}</span></td>
                        <td>
                          <span className={`badge ${cfg.cls}`} style={{ display: 'flex', alignItems: 'center', gap: 5, width: 'fit-content' }}>
                            {cfg.icon} {alert.severity}
                          </span>
                        </td>
                        <td>
                          {alert.videoUrl ? (
                            <button 
                              className="btn btn-secondary btn-sm" 
                              onClick={() => setPlayingVideo(alert.videoUrl!)}
                              style={{ padding: '4px 8px', display: 'flex', gap: '6px', alignItems: 'center' }}
                            >
                              <PlayCircle size={14} /> View
                            </button>
                          ) : (
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>-</span>
                          )}
                        </td>
                        <td style={{ textTransform: 'capitalize' }}>{alert.type}</td>
                        <td style={{ color: 'var(--text-secondary)' }}>{alert.device_name ?? `Device #${alert.device_id}`}</td>
                        <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                          {alert.message}
                        </td>
                        <td>
                          <div style={{ fontSize: '0.78rem' }}>
                            <div>{formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })}</div>
                            <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                              {format(new Date(alert.timestamp), 'MMM d, HH:mm')}
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${alert.resolved ? 'badge-success' : 'badge-danger'}`}>
                            {alert.resolved ? 'Read' : 'Unread'}
                          </span>
                        </td>
                        <td>
                          <div style={{ position: 'relative' }}>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => setOpenDropdown(openDropdown === alert.id ? null : alert.id)}
                              style={{ padding: '4px 8px' }}
                            >
                              <MoreVertical size={14} />
                            </button>
                            {openDropdown === alert.id && (
                              <>
                                <div style={{ position: 'fixed', inset: 0, zIndex: 9 }} onClick={() => setOpenDropdown(null)} />
                                <div style={{
                                  position: 'absolute', right: 0, top: 32, zIndex: 10,
                                  background: 'var(--bg-card)', border: '1px solid var(--border-color)',
                                  borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.5)', width: 140, overflow: 'hidden'
                                }}>
                                  {!alert.resolved ? (
                                    <div className="dropdown-item" onClick={() => handleUpdateStatus(alert.id, true)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', cursor: 'pointer', fontSize: '0.85rem' }}>
                                      <Eye size={14} /> Mark Read
                                    </div>
                                  ) : (
                                    <div className="dropdown-item" onClick={() => handleUpdateStatus(alert.id, false)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', cursor: 'pointer', fontSize: '0.85rem' }}>
                                      <EyeOff size={14} /> Mark Unread
                                    </div>
                                  )}
                                  <div className="dropdown-item" onClick={() => handleDelete(alert.id)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--accent-red)' }}>
                                    <Trash2 size={14} /> Delete
                                  </div>
                                </div>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Video Modal */}
      {playingVideo && (
        <div 
          style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.8)', zIndex: 9999, display: 'flex', justifyContent: 'center', alignItems: 'center' }}
          onClick={() => setPlayingVideo(null)}
        >
          <div 
            style={{ width: '80%', maxWidth: '800px', backgroundColor: '#000', borderRadius: '8px', overflow: 'hidden', position: 'relative' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 10 }}>
              <button 
                onClick={() => setPlayingVideo(null)} 
                style={{ background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '50%', padding: '6px', cursor: 'pointer', color: '#fff', display: 'flex' }}
              >
                <X size={20} />
              </button>
            </div>
            <video 
              src={playingVideo} 
              autoPlay 
              controls 
              style={{ width: '100%', height: 'auto', display: 'block', maxHeight: '80vh' }}
            />
          </div>
        </div>
      )}
    </>
  );
}
