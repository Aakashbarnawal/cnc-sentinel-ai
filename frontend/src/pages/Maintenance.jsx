import React from 'react';
import MaintenanceTable from '../components/MaintenanceTable';

export const Maintenance = ({ maintenanceEvents, machines, onCreateMaintenance }) => {
  return (
    <div>
      <MaintenanceTable
        maintenanceEvents={maintenanceEvents}
        machines={machines}
        onCreateMaintenance={onCreateMaintenance}
      />
    </div>
  );
};

export default Maintenance;
