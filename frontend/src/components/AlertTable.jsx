import React, { useState } from 'react';
import { ShieldAlert, Search, AlertTriangle } from 'lucide-react';
import EmptyState from './EmptyState';

export const AlertTable = ({ predictions = [], telemetry = [] }) => {
  const [searchTerm, setSearchTerm] = useState('');

  // Extract alerts from predictions with high failure risk
  const highRiskPredictions = predictions.filter(
    (p) => p.predicted_class === 1 || p.failure_probability >= p.classification_threshold
  );

  const filteredAlerts = highRiskPredictions.filter((a) =>
    (a.machine_id || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <ShieldAlert size={20} color="var(--status-danger)" />
          <span>High-Risk Predictive Maintenance Alerts</span>
        </div>

        <div className="card-controls">
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="form-input"
              style={{ paddingLeft: '2.1rem', width: '220px' }}
              placeholder="Search Machine ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
      </div>

      {filteredAlerts.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title="No Active High-Risk Alerts"
          description="All monitored machine equipment are currently operating below failure probability thresholds."
        />
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Alert ID</th>
                <th>Machine ID</th>
                <th>Alert Category</th>
                <th>Timestamp</th>
                <th>Failure Probability</th>
                <th>Threshold</th>
                <th>Severity Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredAlerts.map((alert) => (
                <tr key={alert.id}>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>#ALT-{alert.id}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{alert.machine_id || 'UNKNOWN'}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--status-danger)', fontWeight: 600 }}>
                      <AlertTriangle size={15} />
                      <span>{alert.predicted_label}</span>
                    </div>
                  </td>
                  <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    {new Date(alert.created_at).toLocaleString()}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, color: 'var(--status-danger)' }}>
                    {(alert.failure_probability * 100).toFixed(2)}%
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{(alert.classification_threshold * 100).toFixed(0)}%</td>
                  <td>
                    <span className="badge badge-danger">HIGH RISK</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default AlertTable;
