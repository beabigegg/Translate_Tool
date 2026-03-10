import React from 'react';
export function Input({ label, error, className = '', ...props }) {
  return (
    <div className="form-group">
      {label && <label className="form-label">{label}</label>}
      <input className={`form-input ${error ? 'form-input-error' : ''} ${className}`} {...props} />
      {error && <span className="form-error">{error}</span>}
    </div>
  );
}
