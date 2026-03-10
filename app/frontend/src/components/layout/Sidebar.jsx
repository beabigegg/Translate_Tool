import React from 'react';
import { NavLink } from 'react-router-dom';
import { Languages, BookOpen, History, Settings } from 'lucide-react';
import { useHealthCheck } from '../../hooks/useHealthCheck.js';

const NAV_ITEMS = [
  { path: '/', icon: Languages, label: '翻譯' },
  { path: '/terms', icon: BookOpen, label: '術語庫' },
  { path: '/history', icon: History, label: '歷史紀錄' },
  { path: '/settings', icon: Settings, label: '設定' },
];

export function Sidebar() {
  const { isOnline } = useHealthCheck();
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Languages size={24} />
        <span>Translate Tool</span>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ path, icon: Icon, label }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) => `sidebar-nav-item ${isActive ? 'sidebar-nav-item-active' : ''}`}
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div className="health-indicator">
          <span className={`health-dot ${isOnline ? 'health-dot-online' : 'health-dot-offline'}`} />
          <span>{isOnline ? 'Ollama 連線中' : 'Ollama 離線'}</span>
        </div>
      </div>
    </aside>
  );
}
