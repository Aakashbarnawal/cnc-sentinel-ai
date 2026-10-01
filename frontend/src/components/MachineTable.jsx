import React, { useState } from 'react';
import { Cpu, Plus, Search, Eye, Layers } from 'lucide-react';
import { EQUIPMENT_CATEGORIES, DATA_SOURCES } from '../config/equipmentTypes';
import EmptyState from './EmptyState';

export const MachineTable = ({ machines = [], telemetry = [], onRegisterMachine, onSelectMachine }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('ALL');
  const [showModal, setShowModal] = useState(false);
  const [newMachineId, setNewMachineId] = useState('');
  const [newCategory, setNewCategory] = useState('CNC');
  const [errorMsg, setErrorMsg] = useState('');

  // Map latest telemetry per machine
  const latestTelemetryMap = {};
  telemetry.forEach((reading) => {
    if (!latestTelemetryMap[reading.machine_id] || new Date(reading.timestamp) > new Date(latestTelemetryMap[reading.machine_id].timestamp)) {
      latestTelemetryMap[reading.machine_id] = reading;
    }
  });

  const filteredMachines = machines.filter((m) => {
    const matchesSearch = m.machine_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = filterCategory === 'ALL' || m.machine_type === filterCategory;
    return matchesSearch && matchesCategory;
  });

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    if (!newMachineId.trim()) {
      setErrorMsg('Machine ID is required.');
      return;
    }

    const catConfig = EQUIPMENT_CATEGORIES.find((c) => c.id === newCategory) || EQUIPMENT_CATEGORIES[0];

    try {
      await onRegisterMachine({
        machine_id: newMachineId.trim(),
        machine_type: catConfig.backendType, // Map safely to backend accepted enum ('CNC' or '3D_Printer')
      });
      setNewMachineId('');
      setShowModal(false);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to register equipment.');
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Cpu size={20} color="var(--accent-cyan)" />
          <span>CNC Sentinel AI Universal Machine Registry</span>
        </div>

        <div className="card-controls">
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="form-input"
              style={{ paddingLeft: '2.1rem', width: '190px' }}
              placeholder="Search Machine ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <select
            className="form-select"
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
          >
            <option value="ALL">All Machinery Types</option>
            {EQUIPMENT_CATEGORIES.map((cat) => (
              <option key={cat.id} value={cat.backendType}>
                {cat.name}
              </option>
            ))}
          </select>

          <button className="btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={16} />
            <span>Add Equipment</span>
          </button>
        </div>
      </div>

      {filteredMachines.length === 0 ? (
        <EmptyState
          icon={Cpu}
          title="No Industrial Machinery Registered"
          description="Register your first CNC milling spindle, 3D printer, electric motor, or hydraulic pump to begin checking machine pulse."
          actionText="Register New Machinery"
          onAction={() => setShowModal(true)}
        />
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Machine ID</th>
                <th>Category</th>
                <th>Signal Source</th>
                <th>Latest Telemetry</th>
                <th>Health Index</th>
                <th>Pulse Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredMachines.map((m) => {
                const latest = latestTelemetryMap[m.machine_id];
                const health = latest?.health_index;
                const scenario = latest?.scenario || 'normal';
                const sourceTag = latest?.scenario ? DATA_SOURCES.SIMULATED : latest ? DATA_SOURCES.LIVE : DATA_SOURCES.UNAVAILABLE;

                return (
                  <tr key={m.machine_id}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{m.machine_id}</td>
                    <td>
                      <span className={`badge ${m.machine_type === 'CNC' ? 'badge-cnc' : 'badge-printer'}`}>
                        {m.machine_type === 'CNC' ? 'CNC Mill / Motor' : '3D Printer / Fan'}
                      </span>
                    </td>
                    <td>
                      <span className="source-tag" style={{ backgroundColor: sourceTag.bg, color: sourceTag.color }}>
                        {sourceTag.label}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      {latest ? new Date(latest.timestamp).toLocaleString() : 'No readings'}
                    </td>
                    <td>
                      {health !== undefined && health !== null ? (
                        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: health < 50 ? 'var(--status-danger)' : health < 75 ? 'var(--status-warning)' : 'var(--status-normal)' }}>
                          {health.toFixed(1)}%
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>N/A</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${scenario === 'near_failure' ? 'badge-danger' : scenario === 'degrading' ? 'badge-warning' : 'badge-normal'}`}>
                        {scenario === 'near_failure' ? 'CRITICAL PULSE' : scenario === 'degrading' ? 'DEGRADING' : 'HEALTHY PULSE'}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn-refresh"
                        style={{ padding: '0.35rem 0.65rem', fontSize: '0.78rem' }}
                        onClick={() => onSelectMachine(m.machine_id)}
                      >
                        <Eye size={14} />
                        <span>Inspect Pulse</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Universal Registration Modal */}
      {showModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.75)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 100, padding: '1rem',
        }}>
          <div style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.75rem',
            maxWidth: '480px',
            width: '100%',
            boxShadow: 'var(--shadow-lg)',
          }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem', color: 'var(--text-primary)' }}>
              Register Universal Industrial Equipment
            </h3>

            {errorMsg && (
              <div style={{ padding: '0.65rem 0.85rem', backgroundColor: 'var(--status-danger-bg)', color: 'var(--status-danger)', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleRegisterSubmit}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Equipment Identifier (ID)
                </label>
                <input
                  type="text"
                  className="form-input"
                  style={{ width: '100%' }}
                  placeholder="e.g. SPINDLE-CNC-01 or MOTOR-PUMP-03"
                  value={newMachineId}
                  onChange={(e) => setNewMachineId(e.target.value)}
                  required
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Equipment Category
                </label>
                <select
                  className="form-select"
                  style={{ width: '100%' }}
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                >
                  {EQUIPMENT_CATEGORIES.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name} ({cat.description.slice(0, 45)}...)
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  className="btn-refresh"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Confirm Registration
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default MachineTable;
