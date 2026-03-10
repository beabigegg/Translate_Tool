import React from 'react';
export function StatusDot({ status }) {
  const colors = { online: 'status-dot-green', offline: 'status-dot-red', warning: 'status-dot-yellow' };
  return <span className={`status-dot ${colors[status] || ''}`} />;
}
