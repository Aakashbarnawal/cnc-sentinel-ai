import axios from 'axios';

// Dynamic API Base URL resolution for LAN mobile device compatibility
const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  const hostname = window.location.hostname || '127.0.0.1';
  return `http://${hostname}:8000`;
};

const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor to format errors cleanly
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error.response?.data?.detail || error.message || 'API Request Failed';
    return Promise.reject(new Error(detail));
  }
);

export const api = {
  // Base URL helper
  getBaseUrl: getApiBaseUrl,

  // System Health & Readiness
  getHealth: () => apiClient.get('/health'),
  getReadiness: () => apiClient.get('/ready'),

  // Machines API
  getMachines: (params = { limit: 100, offset: 0 }) => apiClient.get('/api/v1/machines', { params }),
  getMachineById: (machineId) => apiClient.get(`/api/v1/machines/${machineId}`),
  registerMachine: (data) => apiClient.post('/api/v1/machines', data),

  // Telemetry API
  getTelemetry: (params = { limit: 100, offset: 0 }) => apiClient.get('/api/v1/telemetry', { params }),
  getTelemetryById: (id) => apiClient.get(`/api/v1/telemetry/${id}`),
  submitTelemetry: (data) => apiClient.post('/api/v1/telemetry', data),
  submitTelemetryBatch: (data) => apiClient.post('/api/v1/telemetry/batch', data),

  // Predictions API
  getPredictions: (params = { limit: 100, offset: 0 }) => apiClient.get('/api/v1/predictions', { params }),
  getPredictionById: (id) => apiClient.get(`/api/v1/predictions/${id}`),
  getLatestPrediction: (machineId) => apiClient.get(`/api/v1/predictions/latest/${machineId}`),
  executePrediction: (data) => apiClient.post('/api/v1/predictions', data),
  explainPrediction: (data) => apiClient.post('/api/v1/predictions/explain', data),

  // Maintenance API
  getMaintenanceEvents: (params = { limit: 100, offset: 0 }) => apiClient.get('/api/v1/maintenance', { params }),
  getMaintenanceById: (id) => apiClient.get(`/api/v1/maintenance/${id}`),
  createMaintenanceEvent: (data) => apiClient.post('/api/v1/maintenance', data),

  // Notifications Integration API (Email & Telegram)
  getNotificationStatus: () => apiClient.get('/api/v1/notifications/status'),
  sendTestEmail: (data) => apiClient.post('/api/v1/notifications/test-email', data),
  sendHealthReportEmail: (data) => apiClient.post('/api/v1/reports/email', data),
  getTelegramStatus: () => apiClient.get('/api/v1/telegram/status'),
  testTelegramMessage: () => apiClient.post('/api/v1/telegram/test'),

  // Digital Twin Simulator Manager API
  getSimulatorStatus: () => apiClient.get('/api/v1/simulator/status'),
  startSimulator: () => apiClient.post('/api/v1/simulator/start'),
  stopSimulator: () => apiClient.post('/api/v1/simulator/stop'),
  setSimulatorScenario: (data) => apiClient.post('/api/v1/simulator/scenario', data),
  setSimulatorSpeed: (data) => apiClient.post('/api/v1/simulator/speed', data),

  // Equipment Diagnostics API
  evaluateDiagnostics: (data) => apiClient.post('/api/v1/diagnostics', data),
};

export default api;
