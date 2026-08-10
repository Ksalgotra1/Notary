import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import LandingPage from './pages/LandingPage';
import GeneratePage from './pages/GeneratePage';
import LibraryPage from './pages/LibraryPage';
import AssetPage from './pages/AssetPage';
import PublicVerifyPage from './pages/PublicVerifyPage';
import DashboardPage from './pages/DashboardPage';
import DocumentationPage from './pages/DocumentationPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/docs" element={<DocumentationPage />} />
            <Route path="/app" element={<GeneratePage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/assets/:runId" element={<AssetPage />} />
            <Route path="/verify/:runId" element={<PublicVerifyPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
