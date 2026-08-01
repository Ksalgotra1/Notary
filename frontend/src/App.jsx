import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import GeneratePage from './pages/GeneratePage';
import LibraryPage from './pages/LibraryPage';
import AssetPage from './pages/AssetPage';
import PublicVerifyPage from './pages/PublicVerifyPage';

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<GeneratePage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/assets/:runId" element={<AssetPage />} />
        <Route path="/verify/:runId" element={<PublicVerifyPage />} />
      </Routes>
    </BrowserRouter>
  );
}
