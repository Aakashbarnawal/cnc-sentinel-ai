import React from 'react';
import DeviceConnections from '../components/DeviceConnections';

export const DeviceConnectionsPage = ({ machines, telemetry }) => {
  return (
    <div>
      <DeviceConnections machines={machines} telemetry={telemetry} />
    </div>
  );
};

export default DeviceConnectionsPage;
