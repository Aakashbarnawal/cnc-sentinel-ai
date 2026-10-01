import React from 'react';
import PredictionPanel from '../components/PredictionPanel';

export const Predictions = ({ predictions, machines, onExecutePrediction, onExplainPrediction }) => {
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

export default Predictions;
