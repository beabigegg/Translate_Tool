import React from 'react';

export function Button({ children, variant = 'primary', size = 'md', disabled, onClick, type = 'button', className = '', ...props }) {
  const base = 'btn';
  const variants = { primary: 'btn-primary', secondary: 'btn-secondary', ghost: 'btn-ghost', danger: 'btn-danger' };
  const sizes = { sm: 'btn-sm', md: '', lg: 'btn-lg' };
  return (
    <button
      type={type}
      className={`${base} ${variants[variant] || ''} ${sizes[size] || ''} ${className}`}
      disabled={disabled}
      onClick={onClick}
      {...props}
    >
      {children}
    </button>
  );
}
