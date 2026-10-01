import React from 'react';

export const LoadingState = ({ message = 'Loading dashboard data...' }) => {
  return (
    <div className="state-container">
      <div className="spinner"></div>
      <p style={{ fontSize: '0.95rem', fontWeight: 500 }}>{message}</p>
    </div>
  );
};

export default LoadingState;
