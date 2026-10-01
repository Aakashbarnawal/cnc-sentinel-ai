import React, { useState } from 'react';
import { Cpu, Activity, ShieldAlert, BrainCircuit, Wrench, HeartPulse, X } from 'lucide-react';
import MetricCard from '../components/MetricCard';
import SensorChart from '../components/SensorChart';
import MachineTable from '../components/MachineTable';
import ScenarioSimulator from '../components/ScenarioSimulator';
import AlertTable from '../components/AlertTable';
import LastGoodHourPanel from '../components/LastGoodHourPanel';

export const Overview = ({
  machines,
  telemetry,
  predictions,
  maintenance,
  selectedMachine,
  onSelectMachine,
  onRegisterMachine,
  onSubmitTelemetry,
}) => {
  const [dismissedAlerts, setDismissedAlerts] = useState([]);
  const totalMachines = machines.length;
  const cncCount = machines.filter((m) => m.machine_type === 'CNC').length;
  const printerCount = machines.filter((m) => m.machine_type === '3D_Printer').length;

  const validHealths = telemetry
    .map((t) => t.health_index)
    .filter((h) => h !== undefined && h !== null);

  const avgHealth = validHealths.length > 0
    ? (validHealths.reduce((a, b) => a + b, 0) / validHealths.length).toFixed(1) + '%'
    : 'N/A';

  const highRiskPredictions = predictions.filter(
    (p) =>
      (p.predicted_class === 1 || p.failure_probability >= (p.classification_threshold || 0.33)) &&
      !dismissedAlerts.includes(p.id)
  );

  const highRiskCount = highRiskPredictions.length;
  const topAlert = highRiskPredictions[0] || null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Active High-Risk Alert Banner */}
      {topAlert ? (
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'var(--status-danger-bg)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <ShieldAlert size={28} color="var(--status-danger)" />
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <span className="badge badge-danger">CRITICAL PULSE ALERT</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.9rem' }}>
                  {topAlert.machine_id ? `Target: ${topAlert.machine_id}` : 'Standalone Benchmark'}
                </span>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  {new Date(topAlert.created_at).toLocaleString()}
                </span>
              </div>
              <div style={{ fontSize: '0.88rem', color: 'var(--text-primary)' }}>
                XGBoost classifier estimates a <b>{(topAlert.failure_probability * 100).toFixed(1)}%</b> failure probability (exceeding {topAlert.classification_threshold * 100}% decision threshold). Immediate inspection recommended.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {topAlert.machine_id && (
              <button
                className="btn-primary"
                style={{ backgroundColor: 'var(--status-danger)', border: 'none', whiteSpace: 'nowrap' }}
                onClick={() => onSelectMachine(topAlert.machine_id)}
              >
                <span>Inspect Pulse</span>
              </button>
            )}
            <button
              className="btn-icon"
              title="Dismiss Alert"
              onClick={() => setDismissedAlerts((prev) => [...prev, topAlert.id])}
              style={{
                background: 'rgba(255, 255, 255, 0.08)',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                padding: '0.45rem',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'background 0.2s, color 0.2s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = '#fff';
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.18)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--text-muted)';
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>
      ) : (
        <div
          style={{
            padding: '1rem 1.5rem',
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'var(--status-normal-bg)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <ShieldAlert size={22} color="var(--status-normal)" />
          <div style={{ fontSize: '0.88rem', color: 'var(--status-normal)', fontWeight: 600 }}>
            Operational Baseline Healthy — Zero Active High-Risk Failure Alerts
          </div>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        <MetricCard
          title="Total Registered Machinery"
          value={totalMachines}
          subtext={`${cncCount} CNC / Motors • ${printerCount} Printers / Fans`}
          icon={Cpu}
          color="var(--accent-cyan)"
        />
        <MetricCard
          title="Monitored Sensor Stream"
          value={telemetry.length}
          subtext="Persisted Sensor Readings"
          icon={Activity}
          color="var(--accent-indigo)"
        />
        <MetricCard
          title="Fleet Health Index"
          value={avgHealth}
          subtext="Ground-truth machine pulse"
          icon={HeartPulse}
          color={validHealths.length > 0 && parseFloat(avgHealth) < 60 ? 'var(--status-warning)' : 'var(--status-normal)'}
        />
        <MetricCard
          title="AI Diagnostics Executed"
          value={predictions.length}
          subtext="XGBoost Inference Records"
          icon={BrainCircuit}
          color="var(--accent-blue)"
        />
        <MetricCard
          title="High-Risk Alerts"
          value={highRiskCount}
          subtext="Probability >= 33% Threshold"
          icon={ShieldAlert}
          color={highRiskCount > 0 ? 'var(--status-danger)' : 'var(--status-normal)'}
        />
        <MetricCard
          title="Maintenance Events"
          value={maintenance.length}
          subtext="Scheduled & Completed"
          icon={Wrench}
          color="var(--text-secondary)"
        />
      </div>

      {/* Sensor Trend Chart */}
      <SensorChart
        telemetryData={telemetry}
        machines={machines}
        selectedMachine={selectedMachine}
        onSelectMachine={onSelectMachine}
      />

      {/* Last Good Hour Safe Operating Panel */}
      <LastGoodHourPanel
        machineId={selectedMachine}
        predictions={predictions}
        telemetry={telemetry}
      />

      {/* Scenario Simulator */}
      <ScenarioSimulator
        machines={machines}
        onSubmitTelemetry={onSubmitTelemetry}
      />

      {/* Machines Overview */}
      <MachineTable
        machines={machines}
        telemetry={telemetry}
        onRegisterMachine={onRegisterMachine}
        onSelectMachine={onSelectMachine}
      />

      {/* Alert Table */}
      <AlertTable predictions={predictions} telemetry={telemetry} />
    </div>
  );
};

export default Overview;
