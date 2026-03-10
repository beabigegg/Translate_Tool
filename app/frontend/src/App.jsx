import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell.jsx';
import { SettingsProvider } from './contexts/SettingsContext.jsx';
import { ErrorBoundary } from './components/feedback/ErrorBoundary.jsx';

const TranslatePage = React.lazy(() => import('./pages/TranslatePage.jsx'));
const TermsPage = React.lazy(() => import('./pages/TermsPage.jsx'));
const TermsReviewPage = React.lazy(() => import('./pages/TermsReviewPage.jsx'));
const SettingsPage = React.lazy(() => import('./pages/SettingsPage.jsx'));
const HistoryPage = React.lazy(() => import('./pages/HistoryPage.jsx'));

function LazyPage({ children }) {
  return (
    <React.Suspense fallback={<div className="page-loading">載入中...</div>}>
      <ErrorBoundary>{children}</ErrorBoundary>
    </React.Suspense>
  );
}

export default function App() {
  return (
    <SettingsProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<LazyPage><TranslatePage /></LazyPage>} />
            <Route path="/terms" element={<LazyPage><TermsPage /></LazyPage>} />
            <Route path="/terms/review" element={<LazyPage><TermsReviewPage /></LazyPage>} />
            <Route path="/settings" element={<LazyPage><SettingsPage /></LazyPage>} />
            <Route path="/history" element={<LazyPage><HistoryPage /></LazyPage>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </SettingsProvider>
  );
}
