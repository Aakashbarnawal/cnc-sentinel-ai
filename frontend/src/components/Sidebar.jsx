import React from 'react';
import {
  LayoutDashboard,
  Cpu,
  Activity,
  BrainCircuit,
  AlertTriangle,
  Wrench,
  Wifi,
  Settings,
  Activity as PulseIcon,
} from 'lucide-react';

export const Sidebar = ({ activeTab, setActiveTab, isOpen, setIsOpen }) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'registry', label: 'Equipment Registry', icon: Cpu },
    { id: 'telemetry', label: 'Live Sensor Monitoring', icon: Activity },
    { id: 'predictions', label: 'Fault Detection & AI', icon: BrainCircuit },
    { id: 'alerts', label: 'Alerts & Incidents', icon: AlertTriangle },
    { id: 'maintenance', label: 'Maintenance History', icon: Wrench },
    { id: 'devices', label: 'Device Connections', icon: Wifi },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <div className="nadi-logo-mark pulse-badge">
          <PulseIcon size={22} />
        </div>
        <div>
          <div className="nadi-logo-title">CNC Sentinel AI</div>
          <div className="nadi-logo-tagline">Intelligent Machine Health</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <div
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              onClick={() => {
                setActiveTab(item.id);
                if (setIsOpen) setIsOpen(false);
              }}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </div>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div style={{ fontWeight: 700, color: 'var(--accent-cyan)', letterSpacing: '0.04em' }}>
          CNC Sentinel AI v2.5
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
          Industrial IoT Health Monitor
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
