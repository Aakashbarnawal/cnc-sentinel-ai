import React from 'react';
import MaintenanceTable from '../components/MaintenanceTable';
import LastGoodHourPanel from '../components/LastGoodHourPanel';

export const MaintenancePage = ({ maintenanceEvents, machines, onCreateMaintenance, predictions, telemetry }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <LastGoodHourPanel predictions={predictions} telemetry={telemetry} />

      <MaintenanceTable
        maintenanceEvents={maintenanceEvents}
        machines={machines}
        onCreateMaintenance={onCreateMaintenance}
      />
    </div>
  );
};

export default MaintenancePage;
