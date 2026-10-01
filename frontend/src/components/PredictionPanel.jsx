import React, { useState } from 'react';
import { BrainCircuit, Play, AlertTriangle, CheckCircle, BarChart2, Info, ShieldAlert } from 'lucide-react';
import EmptyState from './EmptyState';

export const PredictionPanel = ({ predictions = [], machines = [], onExecutePrediction, onExplainPrediction }) => {
  const [formData, setFormData] = useState({
    type: 'L',
    air_temperature_c: 25.0,
    process_temperature_c: 35.0,
    rotational_speed_rpm: 1500,
    torque_nm: 40.0,
    tool_wear_min: 100.0,
    machine_id: '',
  });

  const [lastResult, setLastResult] = useState(null);
  const [lastShap, setLastShap] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [historyFilterMachineId, setHistoryFilterMachineId] = useState('ALL');

  // Map latest prediction record ID per machine/standalone
  const sortedPredictions = [...predictions].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const latestPredictionByMachineMap = {};
  sortedPredictions.forEach((p) => {
    const key = p.machine_id || 'STANDALONE';
    if (!latestPredictionByMachineMap[key]) {
      latestPredictionByMachineMap[key] = p.id;
    }
  });

  const filteredPredictions = sortedPredictions.filter((p) => {
    if (historyFilterMachineId === 'ALL') return true;
    if (historyFilterMachineId === 'STANDALONE') return !p.machine_id;
    return p.machine_id === historyFilterMachineId;
  });

  // Derive empirical diagnostic messages based on physical feature thresholds & model output
  const generateDiagnosticInsights = (data, result) => {
    const insights = [];

    if (data.process_temperature_c > 45.0 || data.air_temperature_c > 35.0) {
      insights.push({
        type: 'danger',
        title: 'Thermal Dissipation Exceedance',
        message: `Process temperature (${data.process_temperature_c}°C) is outside baseline operational range. Check cooling lubricant and thermal sensors.`,
      });
    }

    if (data.torque_nm > 60.0) {
      insights.push({
        type: 'warning',
        title: 'High Torque Load Anomaly',
        message: `Observed torque (${data.torque_nm} Nm) indicates heavy mechanical resistance or spindle binding.`,
      });
    }

    if (data.rotational_speed_rpm < 1200 || data.rotational_speed_rpm > 2500) {
      insights.push({
        type: 'warning',
        title: 'Speed Instability Detected',
        message: `Motor speed (${data.rotational_speed_rpm} RPM) exhibits variance outside steady-state operational limits.`,
      });
    }

    if (data.tool_wear_min > 180.0) {
      insights.push({
        type: 'danger',
        title: 'Critical Tool Wear Accumulation',
        message: `Tool wear index (${data.tool_wear_min} min) exceeds recommended preventive replacement interval. Potential tool chatter or breakdown.`,
      });
    }

    if (result && result.predicted_class === 1) {
      insights.push({
        type: 'danger',
        title: 'AI Failure Prediction Warning',
        message: `XGBoost production classifier estimates a ${(result.failure_probability * 100).toFixed(1)}% probability of equipment failure, exceeding the ${result.classification_threshold * 100}% risk threshold. Inspection recommended.`,
      });
    } else if (insights.length === 0) {
      insights.push({
        type: 'info',
        title: 'Operational Baseline Healthy',
        message: 'All sensor features remain within normal operating envelopes. Machine pulse is stable.',
      });
    }

    return insights;
  };

  const handleSubmitPrediction = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setLastShap(null);
    const payload = {
      ...formData,
      machine_id: formData.machine_id && formData.machine_id.trim() !== '' ? formData.machine_id.trim() : null,
      air_temperature_c: parseFloat(formData.air_temperature_c),
      process_temperature_c: parseFloat(formData.process_temperature_c),
      rotational_speed_rpm: parseInt(formData.rotational_speed_rpm, 10),
      torque_nm: parseFloat(formData.torque_nm),
      tool_wear_min: parseFloat(formData.tool_wear_min),
    };

    try {
      const res = await onExecutePrediction(payload);
      setLastResult(res);

      if (onExplainPrediction) {
        try {
          const shapRes = await onExplainPrediction(payload);
          setLastShap(shapRes);
        } catch (shapErr) {
          console.warn('Optional SHAP explanation call:', shapErr);
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to execute failure prediction.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1.5rem' }}>
        {/* Form Card */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="card-header">
            <div className="card-title">
              <BrainCircuit size={20} color="var(--accent-cyan)" />
              <span>CNC Sentinel AI Diagnostics</span>
            </div>
          </div>

          <form onSubmit={handleSubmitPrediction}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Target Machine
                </label>
                <select
                  className="form-select"
                  style={{ width: '100%' }}
                  value={formData.machine_id}
                  onChange={(e) => setFormData({ ...formData, machine_id: e.target.value })}
                >
                  <option value="">Standalone Benchmark (No Machine ID)</option>
                  {machines.map((m) => (
                    <option key={m.machine_id} value={m.machine_id}>
                      {m.machine_id} ({m.machine_type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Product Variant (Type)
                </label>
                <select
                  className="form-select"
                  style={{ width: '100%' }}
                  value={formData.type}
                  onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                >
                  <option value="L">L (Low Quality / 50% volume)</option>
                  <option value="M">M (Medium Quality / 30% volume)</option>
                  <option value="H">H (High Quality / 20% volume)</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Air Temperature (°C)
                </label>
                <input
                  type="number"
                  step="0.1"
                  className="form-input"
                  style={{ width: '100%' }}
                  value={formData.air_temperature_c}
                  onChange={(e) => setFormData({ ...formData, air_temperature_c: e.target.value })}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Process Temperature (°C)
                </label>
                <input
                  type="number"
                  step="0.1"
                  className="form-input"
                  style={{ width: '100%' }}
                  value={formData.process_temperature_c}
                  onChange={(e) => setFormData({ ...formData, process_temperature_c: e.target.value })}
                  required
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Rotational Speed (RPM)
                </label>
                <input
                  type="number"
                  className="form-input"
                  style={{ width: '100%' }}
                  value={formData.rotational_speed_rpm}
                  onChange={(e) => setFormData({ ...formData, rotational_speed_rpm: e.target.value })}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Torque (Nm)
                </label>
                <input
                  type="number"
                  step="0.1"
                  className="form-input"
                  style={{ width: '100%' }}
                  value={formData.torque_nm}
                  onChange={(e) => setFormData({ ...formData, torque_nm: e.target.value })}
                  required
                />
              </div>
            </div>

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Tool Wear Accumulation (min)
              </label>
              <input
                type="number"
                step="1"
                className="form-input"
                style={{ width: '100%' }}
                value={formData.tool_wear_min}
                onChange={(e) => setFormData({ ...formData, tool_wear_min: e.target.value })}
                required
              />
            </div>

            {error && (
              <div style={{ padding: '0.65rem 0.85rem', backgroundColor: 'var(--status-danger-bg)', color: 'var(--status-danger)', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
              <Play size={16} />
              <span>{loading ? 'Executing Inference...' : 'Run CNC Sentinel AI Diagnostics'}</span>
            </button>
          </form>
        </div>

        {/* Diagnostic Output & SHAP Cards */}
        <div className="card" style={{ marginBottom: 0, display: 'flex', flexDirection: 'column' }}>
          <div className="card-header">
            <div className="card-title">
              <BarChart2 size={20} color="var(--accent-indigo)" />
              <span>Inference & Diagnostic Insights</span>
            </div>
          </div>

          {!lastResult ? (
            <EmptyState
              icon={BrainCircuit}
              title="Awaiting Diagnostic Execution"
              description="Select machine parameters and execute prediction to inspect real-time failure probabilities and SHAP explanations."
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', flex: 1 }}>
              {/* Classification Banner */}
              <div
                style={{
                  padding: '1.25rem',
                  borderRadius: 'var(--radius-lg)',
                  backgroundColor: lastResult.predicted_class === 1 ? 'var(--status-danger-bg)' : 'var(--status-normal-bg)',
                  border: `1px solid ${lastResult.predicted_class === 1 ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)'}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                    Machine Diagnostic Status {lastResult.machine_id ? `(${lastResult.machine_id})` : '(Standalone)'}
                  </div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: lastResult.predicted_class === 1 ? 'var(--status-danger)' : 'var(--status-normal)' }}>
                    {lastResult.predicted_label}
                  </div>
                </div>
                {lastResult.predicted_class === 1 ? (
                  <AlertTriangle size={36} color="var(--status-danger)" />
                ) : (
                  <CheckCircle size={36} color="var(--status-normal)" />
                )}
              </div>

              {/* Probability & Threshold Bar */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.85rem 1rem', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Failure Probability</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                    {(lastResult.failure_probability * 100).toFixed(2)}%
                  </div>
                </div>

                <div style={{ backgroundColor: 'var(--bg-dark)', padding: '0.85rem 1rem', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Decision Threshold</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--accent-indigo)' }}>
                    {(lastResult.classification_threshold * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* Diagnostic Message Cards */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                {generateDiagnosticInsights(formData, lastResult).map((diag, idx) => (
                  <div key={idx} className={`diagnostic-card ${diag.type}`}>
                    <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.15rem' }}>
                      {diag.title}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      {diag.message}
                    </div>
                  </div>
                ))}
              </div>

              {/* SHAP Explanation Breakdown */}
              {lastShap && lastShap.shap_values && (
                <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1rem', borderRadius: 'var(--radius-md)', marginTop: '0.5rem' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
                    SHAP Feature Importance Breakdown
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {lastShap.feature_names.map((fname, idx) => {
                      const val = lastShap.shap_values[idx];
                      const absMax = Math.max(...lastShap.shap_values.map((v) => Math.abs(v))) || 1;
                      const pct = (Math.abs(val) / absMax) * 100;
                      const isPositive = val >= 0;

                      return (
                        <div key={fname} style={{ fontSize: '0.78rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.15rem' }}>
                            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{fname}</span>
                            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: isPositive ? 'var(--status-danger)' : 'var(--status-normal)' }}>
                              {isPositive ? `+${val.toFixed(4)}` : val.toFixed(4)}
                            </span>
                          </div>
                          <div style={{ width: '100%', height: '5px', backgroundColor: '#1e293b', borderRadius: '2px', overflow: 'hidden' }}>
                            <div
                              style={{
                                width: `${pct}%`,
                                height: '100%',
                                backgroundColor: isPositive ? 'var(--status-danger)' : 'var(--status-normal)',
                                borderRadius: '2px',
                              }}
                            ></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* History Log Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <BrainCircuit size={20} color="var(--accent-cyan)" />
            <span>CNC Sentinel AI Diagnostics History Log</span>
          </div>

          <div className="card-controls">
            <select
              className="form-select"
              value={historyFilterMachineId}
              onChange={(e) => setHistoryFilterMachineId(e.target.value)}
            >
              <option value="ALL">All Predictions ({predictions.length})</option>
              <option value="STANDALONE">Standalone Benchmark (No Machine ID)</option>
              {machines.map((m) => (
                <option key={m.machine_id} value={m.machine_id}>
                  {m.machine_id} ({m.machine_type})
                </option>
              ))}
            </select>
          </div>
        </div>

        {filteredPredictions.length === 0 ? (
          <EmptyState
            icon={BrainCircuit}
            title="No Prediction History Records"
            description="Run diagnostics or select another machine filter to inspect saved prediction records."
          />
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Record ID</th>
                  <th>Machine ID</th>
                  <th>Timestamp</th>
                  <th>Probability</th>
                  <th>Threshold</th>
                  <th>Classification</th>
                  <th>Model Version</th>
                </tr>
              </thead>
              <tbody>
                {filteredPredictions.map((p) => {
                  const isLatestForMachine = latestPredictionByMachineMap[p.machine_id || 'STANDALONE'] === p.id;
                  return (
                    <tr key={p.id}>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        #REC-{p.id}
                        {isLatestForMachine && (
                          <span
                            className="badge badge-normal"
                            style={{ marginLeft: '0.5rem', fontSize: '0.65rem', padding: '0.1rem 0.35rem' }}
                          >
                            LATEST
                          </span>
                        )}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                        {p.machine_id || <span style={{ color: 'var(--text-muted)' }}>Standalone</span>}
                      </td>
                      <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                        {new Date(p.created_at).toLocaleString()}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: p.failure_probability >= p.classification_threshold ? 'var(--status-danger)' : 'var(--accent-cyan)' }}>
                        {(p.failure_probability * 100).toFixed(2)}%
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{(p.classification_threshold * 100).toFixed(0)}%</td>
                      <td>
                        <span className={`badge ${p.predicted_class === 1 ? 'badge-danger' : 'badge-normal'}`}>
                          {p.predicted_label}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{p.model_name}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default PredictionPanel;
