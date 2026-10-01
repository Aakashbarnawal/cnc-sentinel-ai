import React, { useState, useEffect } from 'react';
import { Settings, Save, Server, Sliders, Mail, Send, AlertTriangle, CheckCircle, RefreshCw, ShieldCheck, FileText } from 'lucide-react';
import api from '../services/api';

export const SettingsPanel = () => {
  const [baseUrl, setBaseUrl] = useState(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000');
  const [pollInterval, setPollInterval] = useState('10');
  const [tempWarn, setTempWarn] = useState('85');
  const [vibWarn, setVibWarn] = useState('6.5');
  const [saved, setSaved] = useState(false);

  // Email Notification States
  const [notificationStatus, setNotificationStatus] = useState(null);
  const [testRecipient, setTestRecipient] = useState('');
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState(null);

  // Machine Health Report States
  const [machinesList, setMachinesList] = useState([]);
  const [reportMachineId, setReportMachineId] = useState('SN-CNC-001');
  const [reportRecipient, setReportRecipient] = useState('');
  const [reportLoading, setReportLoading] = useState(false);
  const [reportResult, setReportResult] = useState(null);

  const fetchNotificationStatus = async () => {
    try {
      const res = await api.getNotificationStatus();
      setNotificationStatus(res);
      if (res?.email?.recipient_redacted && !testRecipient) {
        setTestRecipient(res.email.recipient_redacted);
      }
    } catch (err) {
      console.warn('Could not fetch notification status:', err);
    }
  };

  const fetchMachines = async () => {
    try {
      const res = await api.getMachines({ limit: 50 });
      if (res?.items && res.items.length > 0) {
        setMachinesList(res.items);
        if (!reportMachineId) {
          setReportMachineId(res.items[0].machine_id);
        }
      }
    } catch (err) {
      console.warn('Could not fetch machine list:', err);
    }
  };

  useEffect(() => {
    fetchNotificationStatus();
    fetchMachines();
  }, []);

  const handleSave = (e) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleSendTestEmail = async (e) => {
    e.preventDefault();
    setTestLoading(true);
    setTestResult(null);

    try {
      const payload = testRecipient && !testRecipient.includes('*') ? { recipient_email: testRecipient } : {};
      const res = await api.sendTestEmail(payload);
      setTestResult({ success: true, message: res.message || 'Test email alert delivered successfully!' });
    } catch (err) {
      setTestResult({ success: false, message: err.message || 'Unable to send test email. Check SMTP configuration.' });
    } finally {
      setTestLoading(false);
    }
  };

  const handleSendHealthReport = async (e) => {
    e.preventDefault();
    setReportLoading(true);
    setReportResult(null);

    try {
      const res = await api.sendHealthReportEmail({
        machine_id: reportMachineId,
        recipient_email: reportRecipient,
      });
      setReportResult({ success: true, message: res.message || 'Health report sent successfully.' });
    } catch (err) {
      setReportResult({ success: false, message: err.message || 'Unable to send health report. Check SMTP configuration.' });
    } finally {
      setReportLoading(false);
    }
  };

  const emailInfo = notificationStatus?.email || {};
  const isEmailConfigured = emailInfo.configured;
  const isEmailEnabled = emailInfo.enabled;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* General Settings */}
      <div className="card" style={{ marginBottom: 0 }}>
        <div className="card-header">
          <div className="card-title">
            <Settings size={20} color="var(--accent-cyan)" />
            <span>CNC Sentinel AI Platform Configuration &amp; Thresholds</span>
          </div>
        </div>

        <form onSubmit={handleSave}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>
            {/* API Server Config */}
            <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1.25rem', borderRadius: 'var(--radius-lg)' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Server size={16} color="var(--accent-cyan)" />
                <span>FastAPI Backend Base URL</span>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Service Endpoint URL
                </label>
                <input
                  type="text"
                  className="form-input"
                  style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Auto-Sync Interval (seconds)
                </label>
                <select
                  className="form-select"
                  style={{ width: '100%' }}
                  value={pollInterval}
                  onChange={(e) => setPollInterval(e.target.value)}
                >
                  <option value="5">5 Seconds (High Frequency)</option>
                  <option value="10">10 Seconds (Standard)</option>
                  <option value="30">30 Seconds (Low Load)</option>
                  <option value="0">Manual Refresh Only</option>
                </select>
              </div>
            </div>

            {/* Thresholds Config */}
            <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1.25rem', borderRadius: 'var(--radius-lg)' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sliders size={16} color="var(--accent-indigo)" />
                <span>Configurable Warning Thresholds</span>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Max Thermal Limit (°C)
                </label>
                <input
                  type="number"
                  className="form-input"
                  style={{ width: '100%' }}
                  value={tempWarn}
                  onChange={(e) => setTempWarn(e.target.value)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Max Vibration Threshold (mm/s RMS)
                </label>
                <input
                  type="number"
                  step="0.1"
                  className="form-input"
                  style={{ width: '100%' }}
                  value={vibWarn}
                  onChange={(e) => setVibWarn(e.target.value)}
                />
              </div>
            </div>
          </div>

          {saved && (
            <div style={{ padding: '0.75rem 1rem', backgroundColor: 'var(--status-normal-bg)', color: 'var(--status-normal)', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle size={18} />
              <span>Platform settings saved successfully.</span>
            </div>
          )}

          <button type="submit" className="btn-primary">
            <Save size={16} />
            <span>Save Settings</span>
          </button>
        </form>
      </div>

      {/* SMTP Email Alert System Management Card */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Mail size={20} color="var(--accent-indigo)" />
            <span>SMTP Email Alert &amp; Report Management</span>
          </div>

          <button className="btn-refresh" onClick={fetchNotificationStatus}>
            <RefreshCw size={14} />
            <span>Check Status</span>
          </button>
        </div>

        {/* Status banner when SMTP is not configured */}
        {!isEmailConfigured && (
          <div style={{ padding: '0.75rem 1rem', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', color: 'var(--status-danger)', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangle size={18} />
            <span>Email notifications unavailable — SMTP not configured in backend environment.</span>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
          {/* Email Status Overview */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1.25rem', borderRadius: 'var(--radius-lg)' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldCheck size={16} color="var(--accent-cyan)" />
              <span>SMTP Integration Status</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', fontSize: '0.82rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.4rem', borderBottom: '1px solid var(--border-color)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Integration State:</span>
                <span className={`badge ${isEmailConfigured && isEmailEnabled ? 'badge-normal' : isEmailConfigured ? 'badge-warning' : 'badge-danger'}`}>
                  {emailInfo.status_label || 'Not Configured'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.4rem', borderBottom: '1px solid var(--border-color)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>SMTP Server:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {emailInfo.smtp_host || 'smtp.gmail.com'} ({emailInfo.smtp_port || 587})
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '0.4rem', borderBottom: '1px solid var(--border-color)' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Configured Recipient:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {emailInfo.recipient_redacted || 'Not Set'}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Alert Cooldown:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {emailInfo.cooldown_sec || 300} seconds
                </span>
              </div>
            </div>

            <div style={{ marginTop: '1rem', padding: '0.65rem', backgroundColor: '#0f172a', borderRadius: 'var(--radius-md)', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              SMTP credentials are configured securely in backend <code>.env</code> file (e.g. <code>SMTP_USERNAME</code>, <code>SMTP_PASSWORD</code>). Secrets are never exposed in browser.
            </div>
          </div>

          {/* Interactive Test Email Delivery */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1.25rem', borderRadius: 'var(--radius-lg)' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Send size={16} color="var(--accent-indigo)" />
              <span>Send User-Triggered Test Email Alert</span>
            </div>

            <form onSubmit={handleSendTestEmail}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Target Recipient Email Address
                </label>
                <input
                  type="email"
                  className="form-input"
                  style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
                  placeholder="e.g. operator@factory.com"
                  value={testRecipient}
                  onChange={(e) => setTestRecipient(e.target.value)}
                  required
                />
              </div>

              {testResult && (
                <div
                  style={{
                    padding: '0.65rem 0.85rem',
                    backgroundColor: testResult.success ? 'var(--status-normal-bg)' : 'var(--status-danger-bg)',
                    color: testResult.success ? 'var(--status-normal)' : 'var(--status-danger)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.82rem',
                    marginBottom: '1rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                >
                  {testResult.success ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
                  <span>{testResult.message}</span>
                </div>
              )}

              <button
                type="submit"
                className="btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
                disabled={testLoading}
              >
                <Send size={16} />
                <span>{testLoading ? 'Sending Test Email...' : 'Send Test Email Notification'}</span>
              </button>
            </form>
          </div>

          {/* Machine Health Report Email Card */}
          <div style={{ backgroundColor: 'var(--bg-dark)', padding: '1.25rem', borderRadius: 'var(--radius-lg)' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <FileText size={16} color="var(--accent-cyan)" />
              <span>Email Machine Health Report</span>
            </div>

            <form onSubmit={handleSendHealthReport}>
              <div style={{ marginBottom: '0.75rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Target Machinery
                </label>
                <select
                  className="form-select"
                  style={{ width: '100%' }}
                  value={reportMachineId}
                  onChange={(e) => setReportMachineId(e.target.value)}
                >
                  {machinesList.length > 0 ? (
                    machinesList.map((m) => (
                      <option key={m.machine_id} value={m.machine_id}>
                        {m.machine_id} ({m.machine_type})
                      </option>
                    ))
                  ) : (
                    <option value="SN-CNC-001">SN-CNC-001 (CNC)</option>
                  )}
                </select>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                  Recipient Email Address
                </label>
                <input
                  type="email"
                  className="form-input"
                  style={{ width: '100%', fontFamily: 'var(--font-mono)' }}
                  placeholder="e.g. supervisor@plant.com"
                  value={reportRecipient}
                  onChange={(e) => setReportRecipient(e.target.value)}
                  required
                />
              </div>

              {reportResult && (
                <div
                  style={{
                    padding: '0.65rem 0.85rem',
                    backgroundColor: reportResult.success ? 'var(--status-normal-bg)' : 'var(--status-danger-bg)',
                    color: reportResult.success ? 'var(--status-normal)' : 'var(--status-danger)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.82rem',
                    marginBottom: '1rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}
                >
                  {reportResult.success ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
                  <span>{reportResult.message}</span>
                </div>
              )}

              <button
                type="submit"
                className="btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
                disabled={reportLoading}
              >
                <FileText size={16} />
                <span>{reportLoading ? 'Compiling & Sending...' : 'Send Health Report'}</span>
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPanel;
