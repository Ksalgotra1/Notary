import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import Sidebar from './components/Sidebar';
import GeneratePage from './pages/GeneratePage';
import LibraryPage from './pages/LibraryPage';
import AssetPage from './pages/AssetPage';
import PublicVerifyPage from './pages/PublicVerifyPage';
import DashboardPage from './pages/DashboardPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<GeneratePage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/assets/:runId" element={<AssetPage />} />
            <Route path="/verify/:runId" element={<PublicVerifyPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </main>
      </div>
      <Analytics />
    </BrowserRouter>
  );
}
