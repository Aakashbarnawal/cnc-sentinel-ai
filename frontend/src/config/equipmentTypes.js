// Universal Equipment & Sensor Configuration for CNC Sentinel AI

export const EQUIPMENT_CATEGORIES = [
  {
    id: 'CNC',
    name: 'CNC Milling Machine & Spindle',
    backendType: 'CNC',
    icon: 'Cpu',
    description: 'High-precision multi-axis metal & composite milling spindle center',
    manufacturers: ['Haas Automation', 'DMG Mori', 'Mazak', 'Fanuc'],
    supportedSensors: ['temp', 'vibration', 'current', 'rpm', 'tool_wear', 'sound', 'pressure'],
    defaultThresholds: { temp: 85, vibration: 6.5, current: 25.0, rpm: 18000, tool_wear: 0.8 },
  },
  {
    id: '3D_Printer',
    name: 'Industrial 3D Printer',
    backendType: '3D_Printer',
    icon: 'Printer',
    description: 'Additive manufacturing FDM/SLS printer bed & extrusion nozzle assembly',
    manufacturers: ['Stratasys', 'EOS', 'Markforged', 'UltiMaker'],
    supportedSensors: ['temp', 'vibration', 'current', 'humidity', 'workload'],
    defaultThresholds: { temp: 110, vibration: 4.0, current: 15.0, workload: 95 },
  },
  {
    id: 'ELECTRIC_MOTOR',
    name: 'Industrial Electric Motor',
    backendType: 'CNC',
    icon: 'Zap',
    description: '3-Phase AC induction motor powering heavy industrial machinery drive trains',
    manufacturers: ['Siemens', 'ABB', 'WEG', 'Schneider Electric'],
    supportedSensors: ['temp', 'vibration', 'current', 'rpm', 'sound'],
    defaultThresholds: { temp: 90, vibration: 5.5, current: 40.0, rpm: 3600 },
  },
  {
    id: 'PUMP_COMPRESSOR',
    name: 'Hydraulic Pump & Compressor',
    backendType: 'CNC',
    icon: 'Activity',
    description: 'Positive displacement fluid pump and high-pressure air compressor unit',
    manufacturers: ['Grundfos', 'Atlas Copco', 'Flowserve', 'Sulzer'],
    supportedSensors: ['temp', 'vibration', 'pressure', 'flow_rate', 'current'],
    defaultThresholds: { temp: 80, vibration: 7.0, pressure: 12.0, current: 30.0 },
  },
  {
    id: 'HVAC_FAN',
    name: 'Blower Fan & HVAC System',
    backendType: '3D_Printer',
    icon: 'Wind',
    description: 'Heavy ventilation exhaust fan and cleanroom air handling unit',
    manufacturers: ['Trane', 'Carrier', 'Daikin', 'FläktGroup'],
    supportedSensors: ['temp', 'vibration', 'rpm', 'pressure', 'humidity'],
    defaultThresholds: { temp: 70, vibration: 4.5, rpm: 2400 },
  },
  {
    id: 'CONVEYOR',
    name: 'Conveyor Drive System',
    backendType: 'CNC',
    icon: 'Layers',
    description: 'Automated material handling belt drive and roller gearbox assembly',
    manufacturers: ['Dematic', 'Honeywell Intelligrated', 'Interroll'],
    supportedSensors: ['temp', 'vibration', 'current', 'speed', 'workload'],
    defaultThresholds: { temp: 75, vibration: 5.0, current: 20.0 },
  },
  {
    id: 'GEARBOX',
    name: 'Bearing & Gearbox Unit',
    backendType: 'CNC',
    icon: 'Settings',
    description: 'High-torque planetary gearbox and ceramic roller bearing housing',
    manufacturers: ['SKF', 'Timken', 'NSK', 'Bonfiglioli'],
    supportedSensors: ['temp', 'vibration', 'acoustic', 'oil_level'],
    defaultThresholds: { temp: 95, vibration: 8.0 },
  },
];

export const SENSOR_TYPES = [
  { id: 'temp', label: 'Temperature', unit: '°C', icon: 'Thermometer', color: '#ef4444' },
  { id: 'vibration', label: 'Vibration RMS', unit: 'mm/s', icon: 'Activity', color: '#f59e0b' },
  { id: 'current', label: 'Electrical Current', unit: 'A', icon: 'Zap', color: '#38bdf8' },
  { id: 'rpm', label: 'Rotational Speed', unit: 'RPM', icon: 'RotateCw', color: '#818cf8' },
  { id: 'sound', label: 'Acoustic Noise', unit: 'dB', icon: 'Volume2', color: '#ec4899' },
  { id: 'pressure', label: 'Fluid Pressure', unit: 'bar', icon: 'Gauge', color: '#10b981' },
  { id: 'humidity', label: 'Relative Humidity', unit: '%', icon: 'Droplets', color: '#06b6d4' },
  { id: 'tool_wear', label: 'Tool Wear Index', unit: 'Index', icon: 'Scissors', color: '#d97706' },
  { id: 'hours', label: 'Operating Hours', unit: 'h', icon: 'Clock', color: '#64748b' },
  { id: 'workload', label: 'Operational Workload', unit: '%', icon: 'BarChart', color: '#a855f7' },
  { id: 'health_index', label: 'Ground-Truth Health', unit: '%', icon: 'HeartPulse', color: '#10b981' },
];

export const DATA_SOURCES = {
  LIVE: { label: 'LIVE DEVICE', color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)', isPhysical: true },
  SIMULATED: { label: 'SIMULATION — NOT LIVE HARDWARE DATA', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)', isPhysical: false },
  HISTORICAL: { label: 'HISTORICAL', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.15)', isPhysical: false },
  UNAVAILABLE: { label: 'UNAVAILABLE', color: '#64748b', bg: 'rgba(100, 116, 139, 0.15)', isPhysical: false },
};

export const PROTOCOL_GATEWAYS = [
  { id: 'esp32_wifi', name: 'ESP32 IoT Sensor Node', protocol: 'HTTP REST / JSON', status: 'Ready for Connection' },
  { id: 'mqtt_broker', name: 'Industrial MQTT Broker', protocol: 'MQTT v5.0 / TLS', status: 'Broker Integration Ready' },
  { id: 'modbus_tcp', name: 'Modbus TCP / Fieldbus Gateway', protocol: 'Modbus TCP / IP', status: 'PLC Gateway Ready' },
  { id: 'opc_ua', name: 'OPC UA Industrial Server', protocol: 'OPC UA Binary', status: 'SCADA Integration Ready' },
];
