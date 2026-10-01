import React from 'react';
import AlertTable from '../components/AlertTable';

export const AlertsIncidents = ({ predictions, telemetry }) => {
  return (
    <div>
      <AlertTable predictions={predictions} telemetry={telemetry} />
    </div>
  );
};

export default AlertsIncidents;
