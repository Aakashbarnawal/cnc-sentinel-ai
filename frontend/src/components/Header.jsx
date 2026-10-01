import React, { useState, useEffect } from 'react';
import { RefreshCw, Menu, Radio, MessageSquare } from 'lucide-react';
import api from '../services/api';

export const Header = ({ title, status, lastRefreshed, onRefresh, toggleMobileMenu }) => {
  const [telegramInfo, setTelegramInfo] = useState(null);

  useEffect(() => {
    api.getTelegramStatus()
      .then(res => setTelegramInfo(res))
      .catch(() => setTelegramInfo(null));
  }, [lastRefreshed]);

  const getStatusClass = () => {
    if (status === 'connected' || status === 'ready') return 'connected';
    if (status === 'degraded') return 'degraded';
    return 'disconnected';
  };

  const getStatusLabel = () => {
    if (status === 'connected' || status === 'ready') return 'Signal Online';
    if (status === 'degraded') return 'Database Degraded';
    return 'Signal Offline';
  };

  return (
    <header className="header">
      <div className="header-title-container">
        <button className="mobile-menu-btn" onClick={toggleMobileMenu} aria-label="Toggle Navigation">
          <Menu size={22} />
        </button>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h1 className="header-title">{title}</h1>
          </div>
        </div>
      </div>

      <div className="header-actions">
        {/* Telegram Status Badge */}
        <div className="mobile-hide" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.35rem',
          padding: '0.3rem 0.65rem',
          borderRadius: 'var(--radius-full)',
          fontSize: '0.78rem',
          fontWeight: 600,
          backgroundColor: telegramInfo?.enabled && telegramInfo?.configured ? 'rgba(16, 185, 129, 0.12)' : 'rgba(100, 116, 139, 0.12)',
          color: telegramInfo?.enabled && telegramInfo?.configured ? 'var(--status-normal)' : 'var(--text-muted)',
          border: `1px solid ${telegramInfo?.enabled && telegramInfo?.configured ? 'rgba(16, 185, 129, 0.25)' : 'var(--border-color)'}`,
        }}>
          <MessageSquare size={13} />
          <span>{telegramInfo?.enabled && telegramInfo?.configured ? 'Telegram Bot Ready' : 'Telegram Off'}</span>
        </div>

        {/* Backend Status Badge */}
        <div className={`status-badge ${getStatusClass()}`}>
          <span className="status-dot"></span>
          <span>{getStatusLabel()}</span>
        </div>

        {lastRefreshed && (
          <div className="mobile-hide" style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Radio size={12} color="var(--accent-cyan)" />
            <span>Pulse: {lastRefreshed.toLocaleTimeString()}</span>
          </div>
        )}

        <button className="btn-refresh" onClick={onRefresh} title="Sync CNC Sentinel AI Signal">
          <RefreshCw size={14} />
          <span className="mobile-hide">Refresh</span>
        </button>
      </div>
    </header>
  );
};

export default Header;
