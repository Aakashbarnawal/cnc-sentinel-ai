import React, { useState, useEffect } from 'react';
import { Sliders, Send, RefreshCw, CheckCircle, AlertOctagon, Info, Play, Square, Zap } from 'lucide-react';
import api from '../services/api';

export const ScenarioSimulator = ({ machines = [], onSubmitTelemetry }) => {
  const [selectedMachine, setSelectedMachine] = useState('');
  const [scenario, setScenario] = useState('normal');
  const [speedFactor, setSpeedFactor] = useState(1.0);
  const [simRunning, setSimRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Default sensor baselines according to operational scenarios
  const scenarioDefaults = {
    normal: { temp: 42.0, vibration: 1.2, current: 12.0, rpm: 12000, hours: 250.0, workload: 45.0, tool_wear: 15.0, health_index: 95.0 },
    degrading: { temp: 75.0, vibration: 4.8, current: 18.2, rpm: 14500, hours: 1450.0, workload: 82.0, tool_wear: 65.0, health_index: 55.0 },
    near_failure: { temp: 115.0, vibration: 12.5, current: 28.5, rpm: 18000, hours: 3200.0, workload: 98.0, tool_wear: 95.0, health_index: 18.0 },
    sensor_anomaly: { temp: 135.0, vibration: 18.2, current: 45.0, rpm: 450, hours: 2100.0, workload: 90.0, tool_wear: 70.0, health_index: 45.0 },
  };

  const [sensorValues, setSensorValues] = useState(scenarioDefaults.normal);

  useEffect(() => {
    if (machines.length > 0 && !selectedMachine) {
      setSelectedMachine(machines[0].machine_id);
    }
    fetchSimulatorState();
  }, [machines, selectedMachine]);

  const fetchSimulatorState = async () => {
    try {
      const status = await api.getSimulatorStatus();
      setSimRunning(status.is_running);
      setSpeedFactor(status.speed_factor);
    } catch (err) {
      console.error("Failed to fetch simulator status:", err);
    }
  };

  const handleScenarioChange = async (newScenario) => {
    setScenario(newScenario);
    setSensorValues(scenarioDefaults[newScenario] || scenarioDefaults.normal);
    if (selectedMachine) {
      try {
        await api.setSimulatorScenario({ machine_id: selectedMachine, scenario: newScenario });
      } catch (err) {
        console.error("Failed to update simulator scenario:", err);
      }
    }
  };

  const handleSpeedChange = async (newSpeed) => {
    const spd = parseFloat(newSpeed);
    setSpeedFactor(spd);
    try {
      await api.setSimulatorSpeed({ speed_factor: spd });
    } catch (err) {
      console.error("Failed to update simulator speed:", err);
    }
  };

  const handleToggleSimulator = async () => {
    try {
      if (simRunning) {
        await api.stopSimulator();
        setSimRunning(false);
      } else {
        await api.startSimulator();
        setSimRunning(true);
      }
    } catch (err) {
      console.error("Simulator toggle error:", err);
    }
  };

  const handleInputChange = (field, value) => {
    setSensorValues({
      ...sensorValues,
      [field]: parseFloat(value) || value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedMachine) {
      setFeedback({ type: 'error', message: 'Please select or register a machine first.' });
      return;
    }

    setSubmitting(true);
    setFeedback(null);

    const machineObj = machines.find((m) => m.machine_id === selectedMachine);
    const machine_type = machineObj ? machineObj.machine_type : 'CNC';

    const timestamp = new Date().toISOString();

    const payload = {
      machine_id: selectedMachine,
      timestamp: timestamp,
      machine_type: machine_type,
      temp: parseFloat(sensorValues.temp),
      vibration: parseFloat(sensorValues.vibration),
      current: parseFloat(sensorValues.current),
      rpm: parseInt(sensorValues.rpm, 10),
      hours: parseFloat(sensorValues.hours),
      workload: parseFloat(sensorValues.workload),
      tool_wear: parseFloat(sensorValues.tool_wear),
      health_index: parseFloat(sensorValues.health_index),
      scenario: scenario,
    };

    try {
      await onSubmitTelemetry(payload);
      setFeedback({
        type: 'success',
        message: `Synthetic telemetry reading successfully submitted for ${selectedMachine} under '${scenario.toUpperCase()}' scenario.`,
      });
    } catch (err) {
      setFeedback({ type: 'error', message: err.message || 'Telemetry submission failed.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Sliders size={20} color="var(--accent-cyan)" />
          <span>Virtual Machine Digital Twin Simulator</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span className="source-tag" style={{
            backgroundColor: simRunning ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.15)',
            color: simRunning ? 'var(--status-normal)' : 'var(--text-muted)'
          }}>
            {simRunning ? 'BACKGROUND SIMULATION ACTIVE' : 'PAUSED'}
          </span>
          <button
            className={`btn ${simRunning ? 'btn-outline' : 'btn-primary'}`}
            onClick={handleToggleSimulator}
            style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
          >
            {simRunning ? <Square size={13} color="#ef4444" /> : <Play size={13} color="#10b981" />}
            <span>{simRunning ? 'Pause Loop' : 'Start Loop'}</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        {/* Machine, Scenario, & Speed Selector Bar */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem', backgroundColor: 'var(--bg-dark)', padding: '1.25rem', borderRadius: 'var(--radius-lg)' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Target Virtual Machine
            </label>
            <select
              className="form-select"
              style={{ width: '100%' }}
              value={selectedMachine}
              onChange={(e) => setSelectedMachine(e.target.value)}
              required
            >
              {machines.length === 0 && <option value="">No Machines Registered</option>}
              {machines.map((m) => (
                <option key={m.machine_id} value={m.machine_id}>
                  {m.machine_id} ({m.machine_type})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Operational Scenario Mode
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.35rem' }}>
              {[
                { id: 'normal', label: 'NORMAL', color: 'var(--status-normal)' },
                { id: 'degrading', label: 'DEGRADING', color: 'var(--status-warning)' },
                { id: 'near_failure', label: 'NEAR FAILURE', color: 'var(--status-danger)' },
                { id: 'sensor_anomaly', label: 'ANOMALY', color: '#a855f7' },
              ].map((sc) => {
                const isSelected = scenario === sc.id;
                return (
                  <button
                    key={sc.id}
                    type="button"
                    onClick={() => handleScenarioChange(sc.id)}
                    style={{
                      backgroundColor: isSelected ? sc.color : 'var(--bg-card)',
                      color: isSelected ? '#fff' : 'var(--text-secondary)',
                      border: `1px solid ${isSelected ? sc.color : 'var(--border-color)'}`,
                      padding: '0.45rem 0.35rem',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      textTransform: 'uppercase',
                      transition: 'all 0.15s ease',
                      textAlign: 'center'
                    }}
                  >
                    {sc.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Simulation Speed Factor ({speedFactor}x)
            </label>
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              {[0.5, 1.0, 2.0, 5.0].map((spd) => (
                <button
                  key={spd}
                  type="button"
                  onClick={() => handleSpeedChange(spd)}
                  style={{
                    flex: 1,
                    backgroundColor: speedFactor === spd ? 'var(--accent-cyan)' : 'var(--bg-card)',
                    color: speedFactor === spd ? '#000' : 'var(--text-secondary)',
                    border: `1px solid ${speedFactor === spd ? 'var(--accent-cyan)' : 'var(--border-color)'}`,
                    padding: '0.45rem 0.25rem',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  {spd}x
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Sliders Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
          {/* Temperature Slider */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem', fontSize: '0.82rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Operating Temp (°C)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--status-danger)' }}>{sensorValues.temp}°C</span>
            </div>
            <input
              type="range"
              min="-20"
              max="180"
              step="0.5"
              style={{ width: '100%', accentColor: 'var(--status-danger)' }}
              value={sensorValues.temp}
              onChange={(e) => handleInputChange('temp', e.target.value)}
            />
          </div>

          {/* Vibration Slider */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem', fontSize: '0.82rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Vibration Intensity (mm/s)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--status-warning)' }}>{sensorValues.vibration} mm/s</span>
            </div>
            <input
              type="range"
              min="0"
              max="50"
              step="0.1"
              style={{ width: '100%', accentColor: 'var(--status-warning)' }}
              value={sensorValues.vibration}
              onChange={(e) => handleInputChange('vibration', e.target.value)}
            />
          </div>

          {/* Current Slider */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem', fontSize: '0.82rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Current Draw (A)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-cyan)' }}>{sensorValues.current} A</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="0.5"
              style={{ width: '100%', accentColor: 'var(--accent-cyan)' }}
              value={sensorValues.current}
              onChange={(e) => handleInputChange('current', e.target.value)}
            />
          </div>

          {/* RPM Slider */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem', fontSize: '0.82rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Motor Speed (RPM)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-indigo)' }}>{sensorValues.rpm} RPM</span>
            </div>
            <input
              type="range"
              min="0"
              max="30000"
              step="100"
              style={{ width: '100%', accentColor: 'var(--accent-indigo)' }}
              value={sensorValues.rpm}
              onChange={(e) => handleInputChange('rpm', e.target.value)}
            />
          </div>

          {/* Tool Wear Slider */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem', fontSize: '0.82rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Tool / Component Wear Index (%)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--status-warning)' }}>{sensorValues.tool_wear}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              style={{ width: '100%', accentColor: 'var(--status-warning)' }}
              value={sensorValues.tool_wear}
              onChange={(e) => handleInputChange('tool_wear', e.target.value)}
            />
          </div>

          {/* Health Index Slider */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem', fontSize: '0.82rem' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Ground-Truth Health Index</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--status-normal)' }}>{sensorValues.health_index}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="1"
              style={{ width: '100%', accentColor: 'var(--status-normal)' }}
              value={sensorValues.health_index}
              onChange={(e) => handleInputChange('health_index', e.target.value)}
            />
          </div>
        </div>

        {/* Feedback Message */}
        {feedback && (
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.85rem',
              fontWeight: 500,
              marginBottom: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              backgroundColor: feedback.type === 'success' ? 'var(--status-normal-bg)' : 'var(--status-danger-bg)',
              color: feedback.type === 'success' ? 'var(--status-normal)' : 'var(--status-danger)',
              border: `1px solid ${feedback.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            }}
          >
            {feedback.type === 'success' ? <CheckCircle size={18} /> : <AlertOctagon size={18} />}
            <span>{feedback.message}</span>
          </div>
        )}

        <button
          type="submit"
          className="btn-primary"
          style={{ width: '100%', justifyContent: 'center' }}
          disabled={submitting || machines.length === 0}
        >
          <Send size={16} />
          <span>{submitting ? 'Submitting Synthetic Telemetry...' : 'Submit Synthetic Reading to Backend'}</span>
        </button>
      </form>
    </div>
  );
};

export default ScenarioSimulator;
