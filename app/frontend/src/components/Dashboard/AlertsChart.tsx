import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

interface AlertsChartProps {
  labels: string[];
  fallData: number[];
  otherData: number[];
}

export default function AlertsChart({
  labels,
  fallData,
  otherData,
}: AlertsChartProps) {
  const data = {
    labels: labels,
    datasets: [
      {
        label: 'Fall Alerts',
        data: fallData,
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239,68,68,0.12)',
        fill: true,
        tension: 0.45,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: '#ef4444',
        borderWidth: 2,
      },
      {
        label: 'Other Alerts',
        data: otherData,
        borderColor: '#06b6d4',
        backgroundColor: 'rgba(6,182,212,0.08)',
        fill: true,
        tension: 0.45,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: '#06b6d4',
        borderWidth: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          color: '#8892a4',
          font: { family: 'Inter', size: 12 },
          boxWidth: 12,
          boxHeight: 12,
          usePointStyle: true,
          pointStyle: 'circle',
        },
      },
      tooltip: {
        backgroundColor: '#131b2e',
        borderColor: 'rgba(255,255,255,0.08)',
        borderWidth: 1,
        titleColor: '#e8eaf6',
        bodyColor: '#8892a4',
        padding: 12,
        cornerRadius: 10,
      },
    },
    scales: {
      x: {
        grid:   { color: 'rgba(255,255,255,0.04)', drawBorder: false },
        ticks:  { color: '#8892a4', font: { family: 'Inter', size: 11 } },
      },
      y: {
        grid:   { color: 'rgba(255,255,255,0.04)', drawBorder: false },
        ticks:  { color: '#8892a4', font: { family: 'Inter', size: 11 } },
        beginAtZero: true,
      },
    },
  };

  return (
    <div style={{ height: 260 }}>
      <Line data={data} options={options} />
    </div>
  );
}
