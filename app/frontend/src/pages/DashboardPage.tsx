import { useEffect, useState, useMemo } from 'react';
import { Camera, Wifi, Bell, HardDrive } from 'lucide-react';
import TopHeader from '../components/Layout/TopHeader';
import StatCard from '../components/Dashboard/StatCard';
import AlertsChart from '../components/Dashboard/AlertsChart';
import RecentAlertsTable from '../components/Dashboard/RecentAlertsTable';
import { deviceApi, alertApi, type Device, type Alert } from '../services/api';
import { useUnifiedEvents } from '../hooks/useUnifiedEvents';
import { formatDistanceToNow, subDays, format, isAfter, startOfDay } from 'date-fns';

// Mock donut widget
import {
  Chart as ChartJS, ArcElement, Tooltip,
} from 'chart.js';
import { Doughnut } from 'react-chartjs-2';
ChartJS.register(ArcElement, Tooltip);

export default function DashboardPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [alerts,  setAlerts]  = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  // Unified real-time updates
  useUnifiedEvents((evt) => {
    if (evt.type === 'device_status') {
      setDevices(prev => prev.map(d => 
        d.id === evt.data.device_id ? { 
          ...d, 
          status: evt.data.status as 'online' | 'offline',
          provisioning_status: evt.data.provisioning_status ?? d.provisioning_status
        } : d
      ));
    } else if (evt.type === 'alert') {
      // Map backend alert to frontend alert format
      const newAlert: Alert = {
        id: evt.data.id,
        device_id: evt.data.id,
        type: evt.data.label?.toLowerCase() || 'unknown',
        severity: (evt.data.confidence > 0.8 ? 'critical' : (evt.data.confidence > 0.5 ? 'high' : 'medium')) as Alert['severity'],
        message: `Detected ${evt.data.label} with ${(evt.data.confidence * 100).toFixed(0)}% confidence`,
        timestamp: evt.data.occurred_at,
        resolved: false,
      };
      setAlerts(prev => [newAlert, ...prev]);
    }
  });

  const fetchData = async () => {
    try {
      const [d, a] = await Promise.all([
        deviceApi.list().catch(() => [] as Device[]),
        alertApi.list({ limit: '1000' } as Record<string,string>).catch(() => [] as Alert[]),
      ]);
      setDevices(d);
      setAlerts(a);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  // 30-day Analytics logic
  const chartData = useMemo(() => {
    const last30Days = Array.from({ length: 30 }).map((_, i) => {
      const d = subDays(new Date(), 29 - i);
      return format(d, 'MMM dd');
    });

    const fallCounts = new Array(30).fill(0);
    const otherCounts = new Array(30).fill(0);

    const thirtyDaysAgo = startOfDay(subDays(new Date(), 29));

    alerts.forEach(a => {
      const alertDate = new Date(a.timestamp);
      if (isAfter(alertDate, thirtyDaysAgo)) {
        const dayDiff = Math.floor((alertDate.getTime() - thirtyDaysAgo.getTime()) / (1000 * 60 * 60 * 24));
        if (dayDiff >= 0 && dayDiff < 30) {
          if (a.type.toLowerCase() === 'fall') fallCounts[dayDiff]++;
          else otherCounts[dayDiff]++;
        }
      }
    });

    return { labels: last30Days, fall: fallCounts, other: otherCounts };
  }, [alerts]);

  const online  = devices.filter(d => d.status === 'online').length;
  const offline = devices.filter(d => d.status === 'offline').length;
  const activeAlerts   = alerts.filter(a => !a.resolved).length;
  const resolvedAlerts = alerts.filter(a => a.resolved).length;

  const donutData = {
    labels: ['Online', 'Offline', 'Warning'],
    datasets: [{
      data: [online, offline, devices.filter(d => d.status === 'warning').length],
      backgroundColor: ['#10b981', '#ef4444', '#f59e0b'],
      borderColor: 'transparent',
      hoverOffset: 4,
    }],
  };

  const donutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '70%',
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#131b2e',
        titleColor: '#e8eaf6',
        bodyColor: '#8892a4',
        borderColor: 'rgba(255,255,255,0.08)',
        borderWidth: 1,
      },
    },
  };

  return (
    <>
      <TopHeader
        title="Dashboard"
        subtitle={`Last updated: ${formatDistanceToNow(new Date(), { addSuffix: true })}`}
        alertCount={activeAlerts}
        onRefresh={fetchData}
      />
      <div className="page-content">
        {/* ── Stat cards ── */}
        <div className="stat-cards-grid">
          <StatCard
            label="Total Cameras"
            value={loading ? '—' : devices.length}
            icon={<Camera size={20} color="white" />}
            iconBg="linear-gradient(135deg,#3b82f6,#06b6d4)"
            change={12}
            gradient="linear-gradient(135deg,#3b82f6,#06b6d4)"
          />
          <StatCard
            label="Online Cameras"
            value={loading ? '—' : online}
            icon={<Wifi size={20} color="white" />}
            iconBg="linear-gradient(135deg,#10b981,#06b6d4)"
            change={online > 0 ? Math.round(online / (devices.length || 1) * 100) : 0}
            changeLabel="uptime"
            gradient="linear-gradient(135deg,#10b981,#06b6d4)"
          />
          <StatCard
            label="Active Alerts Today"
            value={loading ? '—' : activeAlerts}
            icon={<Bell size={20} color="white" />}
            iconBg="linear-gradient(135deg,#ef4444,#f59e0b)"
            change={-8}
            gradient="linear-gradient(135deg,#ef4444,#f59e0b)"
          />
          <StatCard
            label="Resolved Alerts"
            value={loading ? '—' : resolvedAlerts}
            icon={<HardDrive size={20} color="white" />}
            iconBg="linear-gradient(135deg,#a855f7,#ec4899)"
            change={24}
            gradient="linear-gradient(135deg,#a855f7,#ec4899)"
          />
        </div>

        {/* ── Main chart + Donut ── */}
        <div className="dashboard-grid" style={{ marginBottom: 24 }}>
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Alert Events (Last 30 Days)</div>
                <div className="card-subtitle">Real monitoring data from your devices</div>
              </div>
            </div>
            <AlertsChart 
              labels={chartData.labels}
              fallData={chartData.fall}
              otherData={chartData.other}
            />
          </div>

          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Camera Status</div>
                <div className="card-subtitle">Current device health</div>
              </div>
            </div>
            <div style={{ height: 180, position: 'relative', marginBottom: 16 }}>
              <Doughnut data={donutData} options={donutOptions} />
              <div style={{
                position: 'absolute', top: '50%', left: '50%',
                transform: 'translate(-50%,-50%)', textAlign: 'center',
              }}>
                <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{devices.length}</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Total</div>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { label: 'Online',  count: online,  color: '#10b981' },
                { label: 'Offline', count: offline, color: '#ef4444' },
                { label: 'Warning', count: devices.filter(d => d.status === 'warning').length, color: '#f59e0b' },
              ].map(row => (
                <div key={row.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: row.color, display: 'block' }} />
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{row.label}</span>
                  </div>
                  <span style={{ fontWeight: 600 }}>{row.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Recent Alerts ── */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Recent Alerts</div>
              <div className="card-subtitle">Latest security events</div>
            </div>
            <a href="/alerts" style={{ fontSize: '0.82rem', color: 'var(--accent-purple)' }}>View all →</a>
          </div>
          {loading
            ? <div className="spinner" />
            : <RecentAlertsTable alerts={alerts.slice(0, 8)} />
          }
        </div>
      </div>
    </>
  );
}
