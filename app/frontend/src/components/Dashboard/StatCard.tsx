import { type ReactNode } from 'react';
import { MoreHorizontal, TrendingUp, TrendingDown } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: string | number;
  icon: ReactNode;
  iconBg: string;
  change?: number;
  changeLabel?: string;
  gradient?: string;
}

export default function StatCard({
  label, value, icon, iconBg, change, changeLabel, gradient,
}: StatCardProps) {
  const positive = change !== undefined && change >= 0;

  return (
    <div
      className="stat-card"
      style={{ '--card-gradient': gradient } as React.CSSProperties}
    >
      <div className="stat-card-header">
        <div className="stat-card-icon" style={{ background: iconBg }}>
          {icon}
        </div>
        <button className="stat-card-menu header-action-btn" style={{ width: 28, height: 28 }}>
          <MoreHorizontal size={14} />
        </button>
      </div>

      <div className="stat-card-value">{value}</div>
      <div className="stat-card-label">{label}</div>

      {change !== undefined && (
        <div className={`stat-card-change ${positive ? 'positive' : 'negative'}`}>
          {positive ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
          {Math.abs(change)}% {changeLabel ?? 'vs last week'}
        </div>
      )}
    </div>
  );
}
