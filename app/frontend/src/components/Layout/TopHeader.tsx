import { Bell, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface TopHeaderProps {
  title: string;
  subtitle?: string;
  alertCount?: number;
  onRefresh?: () => void;
}

export default function TopHeader({ title, subtitle, alertCount = 0, onRefresh }: TopHeaderProps) {
  const navigate = useNavigate();

  return (
    <header className="top-header">
      {/* Page title */}
      <div className="header-title">
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>

      {/* Actions */}
      <div className="header-actions">
        {onRefresh && (
          <button className="header-action-btn" onClick={onRefresh} title="Refresh">
            <RefreshCw size={16} />
          </button>
        )}
        <button
          className="header-action-btn"
          title="Notifications"
          onClick={() => navigate('/alerts')}
        >
          <Bell size={16} />
          {alertCount > 0 && <span className="notif-dot" />}
        </button>
      </div>
    </header>
  );
}
