import React from 'react';
export function Checkbox({ label, checked, onChange, disabled, className = '' }) {
  return (
    <label className={`checkbox-label ${className}`}>
      <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} />
      <span>{label}</span>
    </label>
  );
}
