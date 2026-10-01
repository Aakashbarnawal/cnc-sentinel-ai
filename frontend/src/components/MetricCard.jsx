import React from 'react';

export const MetricCard = ({ title, value, subtext, icon: Icon, color = 'var(--accent-cyan)' }) => {
  return (
    <div className="metric-card">
      <div className="metric-card-header">
        <span className="metric-title">{title}</span>
        {Icon && (
          <div
            className="metric-icon-wrapper"
            style={{
              backgroundColor: `${color}1A`, // 10% opacity
              color: color,
            }}
          >
            <Icon size={20} />
          </div>
        )}
      </div>
      <div className="metric-value" style={{ color: color }}>
        {value !== undefined && value !== null ? value : 'N/A'}
      </div>
      {subtext && <div className="metric-subtext">{subtext}</div>}
    </div>
  );
};

export default MetricCard;
