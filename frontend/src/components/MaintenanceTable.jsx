import React, { useState } from 'react';
import { Wrench, Plus, Search, CheckCircle2, Clock, Wrench as ToolIcon } from 'lucide-react';
import EmptyState from './EmptyState';

export const MaintenanceTable = ({ maintenanceEvents = [], machines = [], onCreateMaintenance }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({
    machine_id: machines[0]?.machine_id || '',
    event_type: 'inspection',
    description: '',
    event_timestamp: new Date().toISOString().slice(0, 16),
    status: 'scheduled',
  });
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const filteredEvents = maintenanceEvents.filter((ev) => {
    const matchesSearch = ev.machine_id.toLowerCase().includes(searchTerm.toLowerCase()) || (ev.description || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = filterStatus === 'ALL' || ev.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    if (!formData.machine_id) {
      setErrorMsg('Please select a registered machine.');
      return;
    }

    setSubmitting(true);
    try {
      await onCreateMaintenance({
        ...formData,
        event_timestamp: new Date(formData.event_timestamp).toISOString(),
      });
      setShowModal(false);
      setFormData({
        machine_id: machines[0]?.machine_id || '',
        event_type: 'inspection',
        description: '',
        event_timestamp: new Date().toISOString().slice(0, 16),
        status: 'scheduled',
      });
    } catch (err) {
      setErrorMsg(err.message || 'Failed to schedule maintenance event.');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed':
        return <span className="badge badge-normal"><CheckCircle2 size={12} /> Completed</span>;
      case 'in_progress':
        return <span className="badge badge-warning"><ToolIcon size={12} /> In Progress</span>;
      case 'scheduled':
      default:
        return <span className="badge badge-cnc"><Clock size={12} /> Scheduled</span>;
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Wrench size={20} color="var(--accent-cyan)" />
          <span>Equipment Maintenance History & Logs</span>
        </div>

        <div className="card-controls">
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              className="form-input"
              style={{ paddingLeft: '2.1rem', width: '200px' }}
              placeholder="Search ID or description..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <select
            className="form-select"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="ALL">All Statuses</option>
            <option value="scheduled">Scheduled</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
          </select>

          <button className="btn-primary" onClick={() => setShowModal(true)}>
            <Plus size={16} />
            <span>Schedule Maintenance</span>
          </button>
        </div>
      </div>

      {filteredEvents.length === 0 ? (
        <EmptyState
          icon={Wrench}
          title="No Maintenance Records Found"
          description="Log routine inspections, preventive maintenance, or repairs for registered machines."
          actionText="Log Maintenance Event"
          onAction={() => setShowModal(true)}
        />
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Machine ID</th>
                <th>Event Type</th>
                <th>Description</th>
                <th>Event Date & Time</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map((ev) => (
                <tr key={ev.id}>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>#EVT-{ev.id}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{ev.machine_id}</td>
                  <td>
                    <span style={{ textTransform: 'capitalize', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {ev.event_type}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-secondary)' }}>{ev.description || 'N/A'}</td>
                  <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    {new Date(ev.event_timestamp).toLocaleString()}
                  </td>
                  <td>{getStatusBadge(ev.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Maintenance Creation Modal */}
      {showModal && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
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
              Log Equipment Maintenance Event
            </h3>

            {errorMsg && (
              <div style={{ padding: '0.65rem 0.85rem', backgroundColor: 'var(--status-danger-bg)', color: 'var(--status-danger)', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Target Machine
                </label>
                <select
                  className="form-select"
                  style={{ width: '100%' }}
                  value={formData.machine_id}
                  onChange={(e) => setFormData({ ...formData, machine_id: e.target.value })}
                  required
                >
                  <option value="">Select Machine...</option>
                  {machines.map((m) => (
                    <option key={m.machine_id} value={m.machine_id}>
                      {m.machine_id} ({m.machine_type})
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                    Event Type
                  </label>
                  <select
                    className="form-select"
                    style={{ width: '100%' }}
                    value={formData.event_type}
                    onChange={(e) => setFormData({ ...formData, event_type: e.target.value })}
                  >
                    <option value="inspection">Inspection</option>
                    <option value="maintenance">Preventive Maintenance</option>
                    <option value="repair">Emergency Repair</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                    Initial Status
                  </label>
                  <select
                    className="form-select"
                    style={{ width: '100%' }}
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  >
                    <option value="scheduled">Scheduled</option>
                    <option value="in_progress">In Progress</option>
                    <option value="completed">Completed</option>
                  </select>
                </div>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Event Date & Time
                </label>
                <input
                  type="datetime-local"
                  className="form-input"
                  style={{ width: '100%' }}
                  value={formData.event_timestamp}
                  onChange={(e) => setFormData({ ...formData, event_timestamp: e.target.value })}
                  required
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                  Description / Notes
                </label>
                <textarea
                  className="form-input"
                  style={{ width: '100%', minHeight: '80px', resize: 'vertical' }}
                  placeholder="e.g. Spindle bearing replacement and lubrication check..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                ></textarea>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  className="btn-refresh"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={submitting}>
                  {submitting ? 'Saving Event...' : 'Schedule Event'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default MaintenanceTable;
