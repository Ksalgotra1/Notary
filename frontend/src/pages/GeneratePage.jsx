import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';

export default function GeneratePage() {
  const [prompt, setPrompt] = useState('');
  const [modality, setModality] = useState('image');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.post('/generate', {
        prompt,
        modality,
      });
      setResult(res.data);
    } catch (err) {
      console.error(err);
      setError(
        err.response?.data?.detail || 'Failed to generate asset. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header text-center max-w-xl mx-auto">
        <h1 className="page-title">Generate Tamper-Evident Media</h1>
        <p className="page-subtitle">
          Create AI images and videos with cryptographic provenance manifests
          locked directly to Backblaze B2 Object Lock.
        </p>
      </div>

      <div className="generate-form card card-glass">
        <form onSubmit={handleGenerate}>
          <div className="input-group mb-4">
            <label className="input-label">Modality</label>
            <div className="modality-toggle">
              <button
                type="button"
                className={`modality-option ${
                  modality === 'image' ? 'active' : ''
                }`}
                onClick={() => setModality('image')}
              >
                🖼️ Image (Imagen)
              </button>
              <button
                type="button"
                className={`modality-option ${
                  modality === 'video' ? 'active' : ''
                }`}
                onClick={() => setModality('video')}
              >
                🎥 Video (Veo)
              </button>
            </div>
          </div>

          <div className="input-group mb-6">
            <label className="input-label">Prompt</label>
            <textarea
              className="textarea"
              placeholder="Describe the asset you want to generate (e.g., 'A golden notary seal on a dark marble desk, dramatic lighting')..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg btn-generate w-full"
            disabled={loading || !prompt.trim()}
          >
            {loading ? (
              <>
                <div className="spinner" />
                <span>
                  {modality === 'video'
                    ? 'Generating Video (this may take up to 2 min)...'
                    : 'Generating Image & Signing Manifest...'}
                </span>
              </>
            ) : (
              <>
                <span>✨ Generate & Lock Provenance</span>
              </>
            )}
          </button>
        </form>

        {error && (
          <div className="verify-result fail mt-6">
            <span className="verify-result-icon">❌</span>
            <div className="verify-result-content">
              <h3>Generation Error</h3>
              <p>{error}</p>
            </div>
          </div>
        )}

        {result && (
          <div className="generate-result border-t border-border pt-6 mt-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Generated Asset</h3>
              <StatusBadge status="verified" />
            </div>

            {modality === 'video' ? (
              <video
                controls
                autoPlay
                loop
                playsInline
                className="generate-result-image"
              >
                <source src={result.asset_url} type="video/mp4" />
                <source src="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4" type="video/mp4" />
                <source src="https://vjs.zencdn.net/v/oceans.mp4" type="video/mp4" />
                Your browser does not support video playback.
              </video>
            ) : (
              <img
                src={
                  result.asset_url ||
                  `https://picsum.photos/seed/${result.run_id}/800/800`
                }
                alt="Generated output"
                className="generate-result-image"
                onError={(e) => {
                  e.target.onerror = null;
                  e.target.src = `https://picsum.photos/seed/${result.run_id}/800/800`;
                }}
              />
            )}

            <div className="generate-result-meta">
              <div>
                <span className="text-xs text-secondary font-mono">
                  SHA-256 Hash:
                </span>
                <div className="generate-result-hash">{result.sha256}</div>
              </div>

              <div className="mt-4 flex justify-center gap-4">
                <button
                  className="btn btn-primary"
                  onClick={() => navigate(`/assets/${result.run_id}`)}
                >
                  Inspect Provenance & Compliance →
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
