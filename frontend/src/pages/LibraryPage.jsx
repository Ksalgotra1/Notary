import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Image as ImageIcon, Video as VideoIcon, Layers, FolderOpen, XCircle } from 'lucide-react';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';
import SmartAssetImage from '../components/SmartAssetImage';

export default function LibraryPage() {
  const [assets, setAssets] = useState([]);
  const [filterModality, setFilterModality] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const fetchAssets = useCallback(async () => {
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
  }, [filterModality]);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

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
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <Plus style={{ width: 16, height: 16 }} />
          <span>Generate New Asset</span>
        </button>
      </div>

      <div className="filter-pills">
        <button
          className={`filter-pill ${filterModality === 'all' ? 'active' : ''}`}
          onClick={() => setFilterModality('all')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <Layers style={{ width: 14, height: 14 }} />
          <span>All Modalities</span>
        </button>
        <button
          className={`filter-pill ${filterModality === 'image' ? 'active' : ''}`}
          onClick={() => setFilterModality('image')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <ImageIcon style={{ width: 14, height: 14 }} />
          <span>Images</span>
        </button>
        <button
          className={`filter-pill ${filterModality === 'video' ? 'active' : ''}`}
          onClick={() => setFilterModality('video')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <VideoIcon style={{ width: 14, height: 14 }} />
          <span>Videos</span>
        </button>
      </div>

      {loading ? (
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Loading provenance records...</span>
        </div>
      ) : error ? (
        <div className="verify-result fail">
          <XCircle style={{ width: 24, height: 24, color: '#ff2047', flexShrink: 0 }} />
          <div className="verify-result-content">
            <h3>Library Load Error</h3>
            <p>{error}</p>
          </div>
        </div>
      ) : assets.length === 0 ? (
        <div className="empty-state card">
          <FolderOpen style={{ width: 44, height: 44, opacity: 0.4, marginBottom: 12 }} />
          <div className="empty-state-title" style={{ fontSize: '1.25rem' }}>No Assets Found</div>
          <div className="empty-state-text">
            No generated assets match your current filter. Create your first
            provenance-backed AI asset now.
          </div>
          <button
            className="btn btn-primary"
            onClick={() => navigate('/')}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <Plus style={{ width: 16, height: 16 }} />
            <span>Generate First Asset</span>
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
                  </video>
                </div>
              ) : (
                <SmartAssetImage
                  src={asset.b2_asset_url}
                  alt="Failed to generate asset image"
                  className="asset-card-thumbnail"
                />
              )}
              <div className="asset-card-body">
                <div className="flex justify-between items-center mb-2">
                  <StatusBadge status={asset.modality} type="modality" />
                  <StatusBadge status={asset.verify_status || 'unknown'} />
                </div>
                <div className="asset-card-prompt">{asset.prompt}</div>
                <div className="asset-card-meta mt-3">
                  <span>
                    {asset.provider} / {asset.model ? (asset.model.includes('/') ? asset.model.split('/')[1] : asset.model) : 'standard'}
                  </span>
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
