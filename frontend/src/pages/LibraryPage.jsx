import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';

export default function LibraryPage() {
  const [assets, setAssets] = useState([]);
  const [filterModality, setFilterModality] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchAssets();
  }, [filterModality]);

  const fetchAssets = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (filterModality !== 'all') params.modality = filterModality;
      const res = await api.get('/assets', { params });
      setAssets(res.data.assets);
    } catch (err) {
      console.error(err);
      setError('Failed to load asset library.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header flex justify-between items-center flex-wrap gap-4">
        <div>
          <h1 className="page-title">Provenance Library</h1>
          <p className="page-subtitle">
            All AI assets generated and anchored to immutable B2 Object Lock.
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => navigate('/')}
        >
          + Generate New Asset
        </button>
      </div>

      <div className="filter-pills">
        <button
          className={`filter-pill ${filterModality === 'all' ? 'active' : ''}`}
          onClick={() => setFilterModality('all')}
        >
          All Modalities
        </button>
        <button
          className={`filter-pill ${filterModality === 'image' ? 'active' : ''}`}
          onClick={() => setFilterModality('image')}
        >
          🖼️ Images
        </button>
        <button
          className={`filter-pill ${filterModality === 'video' ? 'active' : ''}`}
          onClick={() => setFilterModality('video')}
        >
          🎥 Videos
        </button>
      </div>

      {loading ? (
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Loading provenance records...</span>
        </div>
      ) : error ? (
        <div className="verify-result fail">
          <span className="verify-result-icon">❌</span>
          <div className="verify-result-content">
            <h3>Library Load Error</h3>
            <p>{error}</p>
          </div>
        </div>
      ) : assets.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-state-icon">📜</div>
          <div className="empty-state-title">No Assets Found</div>
          <div className="empty-state-text">
            No generated assets match your current filter. Create your first
            provenance-backed AI asset now.
          </div>
          <button
            className="btn btn-primary"
            onClick={() => navigate('/')}
          >
            Generate First Asset
          </button>
        </div>
      ) : (
        <div className="asset-grid">
          {assets.map((asset) => (
            <div
              key={asset.run_id}
              className="asset-card"
              onClick={() => navigate(`/assets/${asset.run_id}`)}
            >
              {asset.modality === 'video' ? (
                <div className="asset-card-thumbnail" style={{ position: 'relative', overflow: 'hidden' }}>
                  <video
                    muted
                    loop
                    playsInline
                    autoPlay
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  >
                    <source src={asset.b2_asset_url} type="video/mp4" />
                    <source src="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4" type="video/mp4" />
                  </video>
                </div>
              ) : (
                <img
                  src={
                    asset.b2_asset_url ||
                    `https://picsum.photos/seed/${asset.run_id}/600/600`
                  }
                  alt={asset.prompt}
                  className="asset-card-thumbnail"
                  onError={(e) => {
                    e.target.onerror = null;
                    e.target.src = `https://picsum.photos/seed/${asset.run_id}/600/600`;
                  }}
                />
              )}
              <div className="asset-card-body">
                <div className="flex justify-between items-center mb-2">
                  <StatusBadge status={asset.modality} type="modality" />
                  <StatusBadge status="verified" />
                </div>
                <div className="asset-card-prompt">{asset.prompt}</div>
                <div className="asset-card-meta mt-3">
                  <span>{asset.provider} / {asset.model.split('-')[0]}</span>
                  <span>{new Date(asset.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
