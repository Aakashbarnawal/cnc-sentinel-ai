import React from 'react';
import { Clock, ShieldAlert, AlertTriangle, CheckCircle, ArrowRight, Wrench } from 'lucide-react';

export const LastGoodHourPanel = ({ machineId, predictions = [], telemetry = [] }) => {
  // Filter for specific machine if supplied
  const machineTelemetry = machineId ? telemetry.filter((t) => t.machine_id === machineId) : telemetry;
  const machinePredictions = machineId ? predictions.filter((p) => p.machine_id === machineId) : predictions;

  const latestPred = machineId ? machinePredictions[0] : predictions[0];
  const latestTelem = machineId ? machineTelemetry[0] : telemetry[0];

  const failureProb = latestPred ? latestPred.failure_probability : 0.05;
  const healthIndex = latestTelem?.health_index ?? 95.0;

  // Calculate Last Good Hour / Safe Operating Estimate dynamically
  const estHoursRemaining = Math.max(0, Math.round((healthIndex / 100) * 120 * (1 - failureProb)));
  const isWarning = failureProb >= 0.33 || healthIndex < 60;
  const isCritical = failureProb >= 0.70 || healthIndex < 35;

  const getPriority = () => {
    if (isCritical) return { label: 'P1 - EMERGENCY INSPECTION', color: 'var(--status-danger)' };
    if (isWarning) return { label: 'P2 - SCHEDULE MAINTENANCE', color: 'var(--status-warning)' };
    return { label: 'P3 - ROUTINE MONITORING', color: 'var(--status-normal)' };
  };

  const priority = getPriority();

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Clock size={20} color="var(--accent-cyan)" />
          <span>Last Good Hour & Remaining Safe Operation (RUL)</span>
        </div>
        <span className="source-tag simulated">
          MODEL ESTIMATE — NOT GUARANTEED TIME
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem', marginBottom: '1.25rem' }}>
        {/* Safe Hours Gauge */}
        <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1.25rem', borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            ESTIMATED SAFE OPERATING TIME
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', margin: '0.75rem 0' }}>
            <span style={{ fontSize: '2.5rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: isCritical ? 'var(--status-danger)' : isWarning ? 'var(--status-warning)' : 'var(--accent-cyan)' }}>
              {estHoursRemaining}
            </span>
            <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Hours</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Calculated from ground-truth health index ({healthIndex.toFixed(1)}%) & XGBoost risk score.
          </div>
        </div>

        {/* Priority & Mode */}
        <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1.25rem', borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            SUGGESTED INSPECTION PRIORITY
          </div>
          <div style={{ fontSize: '1.2rem', fontWeight: 800, color: priority.color, margin: '0.75rem 0' }}>
            {priority.label}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Action Window: {isCritical ? 'Within 4 hours' : isWarning ? 'Within 24-48 hours' : 'Next scheduled cycle'}
          </div>
        </div>
      </div>

      {/* Recommended Actions */}
      <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1rem 1.25rem', borderRadius: 'var(--radius-md)' }}>
        <div style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Wrench size={16} color="var(--accent-indigo)" />
          <span>Recommended Preventive Action Protocol</span>
        </div>
        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {isCritical
            ? 'Emergency halt recommended. Inspect spindle bearing assembly, verify acoustic noise signatures, and replace worn tooling immediately.'
            : isWarning
            ? 'Schedule maintenance window. Perform thermal dissipation check, re-grease bearings, and monitor motor current draw curve.'
            : 'Operational baseline healthy. Continue automated telemetry polling and routine scheduled inspections.'}
        </div>
      </div>
    </div>
  );
};

export default LastGoodHourPanel;
