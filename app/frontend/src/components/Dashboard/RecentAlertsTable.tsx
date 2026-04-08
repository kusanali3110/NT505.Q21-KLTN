import { type Alert } from '../../services/api';
import { formatDistanceToNow } from 'date-fns';
import { AlertTriangle, Activity, Eye, ShieldAlert } from 'lucide-react';

interface RecentAlertsTableProps {
  alerts: Alert[];
}

const SEVERITY_CLASS: Record<string, string> = {
  low:      'badge-info',
  medium:   'badge-warning',
  high:     'badge-danger',
  critical: 'badge-danger',
};

const TYPE_ICONS: Record<string, React.ReactNode> = {
  motion:    <Activity size={14} />,
  intrusion: <ShieldAlert size={14} />,
  fall:      <AlertTriangle size={14} />,
};

export default function RecentAlertsTable({ alerts }: RecentAlertsTableProps) {
  if (!alerts.length) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)' }}>
        <Eye size={32} style={{ marginBottom: 8, opacity: 0.4 }} />
        <p>No recent alerts</p>
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>#ID</th>
            <th>Type</th>
            <th>Camera</th>
            <th>Severity</th>
            <th>Time</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map(alert => (
            <tr key={alert.id}>
              <td><span className="table-id">#{alert.id}</span></td>
              <td>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ color: 'var(--accent-purple)' }}>
                    {TYPE_ICONS[alert.type] ?? <Activity size={14} />}
                  </span>
                  {alert.type.charAt(0).toUpperCase() + alert.type.slice(1)}
                </div>
              </td>
              <td style={{ color: 'var(--text-secondary)' }}>
                {alert.device_name ?? `Device #${alert.device_id}`}
              </td>
              <td>
                <span className={`badge ${SEVERITY_CLASS[alert.severity] ?? 'badge-info'}`}>
                  {alert.severity}
                </span>
              </td>
              <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                {formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })}
              </td>
              <td>
                <span className={`badge ${alert.resolved ? 'badge-success' : 'badge-danger'}`}>
                  {alert.resolved ? 'Resolved' : 'Active'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
