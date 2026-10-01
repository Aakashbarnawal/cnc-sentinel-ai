import React from 'react';
import SensorChart from '../components/SensorChart';
import ScenarioSimulator from '../components/ScenarioSimulator';

export const Telemetry = ({ telemetry, machines, selectedMachine, onSelectMachine, onSubmitTelemetry }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <SensorChart
        telemetryData={telemetry}
        machines={machines}
        selectedMachine={selectedMachine}
        onSelectMachine={onSelectMachine}
      />

      <ScenarioSimulator
        machines={machines}
        onSubmitTelemetry={onSubmitTelemetry}
      />
    </div>
  );
};

export default Telemetry;
