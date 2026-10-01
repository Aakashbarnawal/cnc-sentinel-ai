import React, { useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { Activity, Sliders } from 'lucide-react';
import EmptyState from './EmptyState';

export const SensorChart = ({ telemetryData = [], machines = [], selectedMachine, onSelectMachine }) => {
  const [activeMetric, setActiveMetric] = useState('temp');
  const [timeRange, setTimeRange] = useState('ALL');

  const metricsConfig = {
    temp: { label: 'Temperature (°C)', color: '#ef4444', unit: '°C' },
    vibration: { label: 'Vibration (mm/s)', color: '#f59e0b', unit: 'mm/s' },
    current: { label: 'Current Draw (A)', color: '#38bdf8', unit: 'A' },
    rpm: { label: 'Motor Speed (RPM)', color: '#818cf8', unit: 'RPM' },
    health_index: { label: 'Health Index (%)', color: '#10b981', unit: '%' },
  };

  // Filter telemetry by machine if selected
  const machineFiltered = selectedMachine
    ? telemetryData.filter((d) => d.machine_id === selectedMachine)
    : telemetryData;

  // Filter telemetry by time range
  const timeFilteredData = machineFiltered.filter((d) => {
    if (timeRange === 'ALL') return true;
    const ts = new Date(d.timestamp).getTime();
    const now = Date.now();
    if (timeRange === '1H') return ts >= now - 3600 * 1000;
    if (timeRange === '24H') return ts >= now - 24 * 3600 * 1000;
    if (timeRange === '7D') return ts >= now - 7 * 24 * 3600 * 1000;
    return true;
  });

  // Format data for Recharts (chronological left-to-right order)
  const formattedData = [...timeFilteredData]
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .map((item) => ({
      ...item,
      timeFormatted: new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    }));

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Activity size={20} color="var(--accent-cyan)" />
          <span>Real-Time Telemetry Trends</span>
        </div>

        <div className="card-controls">
          {/* Machine Filter Dropdown */}
          <select
            className="form-select"
            value={selectedMachine || ''}
            onChange={(e) => onSelectMachine(e.target.value || null)}
          >
            <option value="">All Machines</option>
            {machines.map((m) => (
              <option key={m.machine_id} value={m.machine_id}>
                {m.machine_id} ({m.machine_type})
              </option>
            ))}
          </select>

          {/* Time Range Selector */}
          <select
            className="form-select"
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
          >
            <option value="ALL">All Time ({timeFilteredData.length})</option>
            <option value="1H">Last 1 Hour</option>
            <option value="24H">Last 24 Hours</option>
            <option value="7D">Last 7 Days</option>
          </select>

          {/* Metric Selector Buttons */}
          <div style={{ display: 'flex', gap: '0.35rem', backgroundColor: 'var(--bg-dark)', padding: '0.25rem', borderRadius: 'var(--radius-md)' }}>
            {Object.keys(metricsConfig).map((key) => {
              const cfg = metricsConfig[key];
              const isSelected = activeMetric === key;
              return (
                <button
                  key={key}
                  onClick={() => setActiveMetric(key)}
                  style={{
                    backgroundColor: isSelected ? cfg.color : 'transparent',
                    color: isSelected ? '#fff' : 'var(--text-secondary)',
                    border: 'none',
                    padding: '0.35rem 0.65rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {key.toUpperCase()}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {formattedData.length === 0 ? (
        <EmptyState
          icon={Sliders}
          title="No Telemetry Data Available"
          description={selectedMachine ? `No readings recorded for machine ${selectedMachine}.` : "Submit synthetic readings using the Scenario Simulator to visualize live telemetry curves."}
        />
      ) : (
        <div style={{ width: '100%', height: 350 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={formattedData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" opacity={0.6} />
              <XAxis dataKey="timeFormatted" stroke="var(--text-muted)" fontSize={12} tickLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--bg-card)',
                  borderColor: 'var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-primary)',
                  boxShadow: 'var(--shadow-lg)',
                }}
                formatter={(val) => [`${val} ${metricsConfig[activeMetric].unit}`, metricsConfig[activeMetric].label]}
                labelFormatter={(label) => `Timestamp: ${label}`}
              />
              <Legend verticalAlign="top" height={36} />
              <Line
                type="monotone"
                dataKey={activeMetric}
                name={metricsConfig[activeMetric].label}
                stroke={metricsConfig[activeMetric].color}
                strokeWidth={2.5}
                dot={{ r: 3, fill: metricsConfig[activeMetric].color }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default SensorChart;
