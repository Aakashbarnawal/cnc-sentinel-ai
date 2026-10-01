import React from 'react';
import PredictionPanel from '../components/PredictionPanel';

export const FaultDetection = ({ predictions, machines, onExecutePrediction, onExplainPrediction }) => {
  return (
    <div>
      <PredictionPanel
        predictions={predictions}
        machines={machines}
        onExecutePrediction={onExecutePrediction}
        onExplainPrediction={onExplainPrediction}
      />
    </div>
  );
};

export default FaultDetection;
