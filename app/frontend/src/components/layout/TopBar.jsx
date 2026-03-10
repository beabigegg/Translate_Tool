import React from 'react';
import { useLocation } from 'react-router-dom';

const PAGE_TITLES = {
  '/': '翻譯工作台',
  '/terms': '術語庫',
  '/terms/review': '術語審核',
  '/history': '翻譯歷史',
  '/settings': '設定',
};

export function TopBar() {
  const { pathname } = useLocation();
  const title = PAGE_TITLES[pathname] || '翻譯工具';
  return (
    <header className="topbar">
      <h1 className="topbar-title">{title}</h1>
    </header>
  );
}
