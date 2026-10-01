import React from 'react';
import MachineTable from '../components/MachineTable';

export const EquipmentRegistry = ({ machines, telemetry, onRegisterMachine, onSelectMachine }) => {
  return (
    <div>
      <MachineTable
        machines={machines}
        telemetry={telemetry}
        onRegisterMachine={onRegisterMachine}
        onSelectMachine={onSelectMachine}
      />
    </div>
  );
};

export default EquipmentRegistry;
