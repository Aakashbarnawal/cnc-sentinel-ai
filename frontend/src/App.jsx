import React, { useState, useEffect, useCallback } from 'react';
import './styles/global.css';
import './styles/dashboard.css';

import Sidebar from './components/Sidebar';
import Header from './components/Header';
import LoadingState from './components/LoadingState';

import Overview from './pages/Overview';
import EquipmentRegistry from './pages/EquipmentRegistry';
import LiveMonitoring from './pages/LiveMonitoring';
import FaultDetection from './pages/FaultDetection';
import AlertsIncidents from './pages/AlertsIncidents';
import MaintenancePage from './pages/MaintenancePage';
import DeviceConnectionsPage from './pages/DeviceConnectionsPage';
import SettingsPage from './pages/SettingsPage';

import api from './services/api';

export const App = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedMachine, setSelectedMachine] = useState(null);
  const [status, setStatus] = useState('connecting');
  const [lastRefreshed, setLastRefreshed] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Core Data States
  const [machines, setMachines] = useState([]);
  const [telemetry, setTelemetry] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [maintenance, setMaintenance] = useState([]);

  // Fetch all dashboard data from backend FastAPI endpoints
  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    try {
      // 1. Health check
      try {
        const healthRes = await api.getHealth();
        setStatus(healthRes.status === 'ok' ? 'connected' : 'degraded');
      } catch (err) {
        setStatus('disconnected');
      }

      // 2. Fetch entities in parallel
      const [machinesRes, telemetryRes, predictionsRes, maintenanceRes] = await Promise.allSettled([
        api.getMachines({ limit: 100 }),
        api.getTelemetry({ limit: 200 }),
        api.getPredictions({ limit: 100 }),
        api.getMaintenanceEvents({ limit: 100 }),
      ]);

      if (machinesRes.status === 'fulfilled') {
        setMachines(machinesRes.value.items || []);
      }
      if (telemetryRes.status === 'fulfilled') {
        setTelemetry(telemetryRes.value.items || []);
      }
      if (predictionsRes.status === 'fulfilled') {
        setPredictions(predictionsRes.value.items || []);
      }
      if (maintenanceRes.status === 'fulfilled') {
        setMaintenance(maintenanceRes.value.items || []);
      }

      setLastRefreshed(new Date());
    } catch (error) {
      console.error('CNC Sentinel AI data sync failure:', error);
      setStatus('disconnected');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Action Handlers
  const handleRegisterMachine = async (data) => {
    const res = await api.registerMachine(data);
    await fetchDashboardData();
    return res;
  };

  const handleSubmitTelemetry = async (data) => {
    const res = await api.submitTelemetry(data);
    await fetchDashboardData();
    return res;
  };

  const handleExecutePrediction = async (data) => {
    const res = await api.executePrediction(data);
    await fetchDashboardData();
    return res;
  };

  const handleExplainPrediction = async (data) => {
    return await api.explainPrediction(data);
  };

  const handleCreateMaintenance = async (data) => {
    const res = await api.createMaintenanceEvent(data);
    await fetchDashboardData();
    return res;
  };

  const renderActivePage = () => {
    if (loading && machines.length === 0 && telemetry.length === 0) {
      return <LoadingState message="Checking CNC Sentinel AI machine pulse signal..." />;
    }

    switch (activeTab) {
      case 'overview':
        return (
          <Overview
            machines={machines}
            telemetry={telemetry}
            predictions={predictions}
            maintenance={maintenance}
            selectedMachine={selectedMachine}
            onSelectMachine={setSelectedMachine}
            onRegisterMachine={handleRegisterMachine}
            onSubmitTelemetry={handleSubmitTelemetry}
          />
        );
      case 'registry':
        return (
          <EquipmentRegistry
            machines={machines}
            telemetry={telemetry}
            onRegisterMachine={handleRegisterMachine}
            onSelectMachine={(id) => {
              setSelectedMachine(id);
              setActiveTab('telemetry');
            }}
          />
        );
      case 'telemetry':
        return (
          <LiveMonitoring
            telemetry={telemetry}
            machines={machines}
            selectedMachine={selectedMachine}
            onSelectMachine={setSelectedMachine}
            onSubmitTelemetry={handleSubmitTelemetry}
          />
        );
      case 'predictions':
        return (
          <FaultDetection
            predictions={predictions}
            machines={machines}
            onExecutePrediction={handleExecutePrediction}
            onExplainPrediction={handleExplainPrediction}
          />
        );
      case 'alerts':
        return (
          <AlertsIncidents
            predictions={predictions}
            telemetry={telemetry}
          />
        );
      case 'maintenance':
        return (
          <MaintenancePage
            maintenanceEvents={maintenance}
            machines={machines}
            onCreateMaintenance={handleCreateMaintenance}
            predictions={predictions}
            telemetry={telemetry}
          />
        );
      case 'devices':
        return (
          <DeviceConnectionsPage
            machines={machines}
            telemetry={telemetry}
          />
        );
      case 'settings':
        return <SettingsPage />;
      default:
        return null;
    }
  };

  const getPageTitle = () => {
    switch (activeTab) {
      case 'overview': return 'CNC Sentinel AI System Overview';
      case 'registry': return 'Universal Machinery Registry';
      case 'telemetry': return 'Live Sensor Pulse Stream';
      case 'predictions': return 'AI Diagnostics & SHAP Explanations';
      case 'alerts': return 'Alerts & Incidents Center';
      case 'maintenance': return 'Equipment Maintenance & RUL';
      case 'devices': return 'Device & Sensor Connectivity';
      case 'settings': return 'Platform Settings & Thresholds';
      default: return 'CNC Sentinel AI';
    }
  };

  return (
    <div className="app-layout">
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isOpen={mobileMenuOpen}
        setIsOpen={setMobileMenuOpen}
      />

      <div className="main-wrapper">
        <Header
          title={getPageTitle()}
          status={status}
          lastRefreshed={lastRefreshed}
          onRefresh={fetchDashboardData}
          toggleMobileMenu={() => setMobileMenuOpen(!mobileMenuOpen)}
        />

        <main className="main-content">
          {renderActivePage()}
        </main>
      </div>
    </div>
  );
};

export default App;
