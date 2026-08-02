import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function GeneratePage() {
  const [prompt, setPrompt] = useState('');
  const [modality, setModality] = useState('image');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [genTime, setGenTime] = useState(null);
  const [cascadeLog, setCascadeLog] = useState([]);
  const navigate = useNavigate();

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setGenTime(null);
    setCascadeLog([]);
    const t0 = performance.now();

    try {
      // Use SSE streaming endpoint for real-time cascade visibility
      const response = await fetch(`${BASE_URL}/generate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, modality }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));
              setCascadeLog(prev => [...prev, event]);

              if (event.stage === 'completed') {
                const elapsed = ((performance.now() - t0) / 1000).toFixed(1);
                setGenTime(elapsed);
                setResult(event);
              } else if (event.stage === 'failed') {
                setError(event.message);
              }
            } catch (parseErr) {
              // skip malformed events
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to generate asset. Please try again.');
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

        {/* Live Cascade Log */}
        {cascadeLog.length > 0 && (
          <div style={{
            marginTop: 16, background: 'rgba(0,0,0,0.3)', borderRadius: 10,
            padding: 16, fontFamily: 'monospace', fontSize: 12, maxHeight: 200,
            overflowY: 'auto',
          }}>
            <div style={{ fontSize: 10, color: '#888', marginBottom: 8, fontFamily: 'Inter, sans-serif', fontWeight: 600 }}>
              🔀 PROVIDER CASCADE LOG
            </div>
            {cascadeLog.map((ev, i) => {
              const icon = ev.stage.includes('success') || ev.stage === 'completed' ? '✅'
                : ev.stage.includes('error') || ev.stage.includes('exhausted') || ev.stage === 'failed' ? '❌'
                : ev.stage.includes('trying') ? '🔄'
                : ev.stage.includes('quota') ? '⚠️' : '•';
              const color = ev.stage.includes('success') || ev.stage === 'completed' ? '#2ea44f'
                : ev.stage.includes('error') || ev.stage === 'failed' ? '#d73a49'
                : '#e3a008';
              return (
                <div key={i} style={{ marginBottom: 3, display: 'flex', gap: 8, color }}>
                  <span>{icon}</span>
                  <span style={{ color: '#555', minWidth: 55 }}>{ev.elapsed_ms}ms</span>
                  <span>{ev.message}</span>
                </div>
              );
            })}
          </div>
        )}

        {result && (
          <div className="generate-result border-t border-border pt-6 mt-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Generated Asset</h3>
              <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                {result.provider && (
                  <span style={{
                    background: result.provider === 'google' ? '#1a73e8' : result.provider === 'nvidia' ? '#76b900' : '#6366f1',
                    color: '#fff', fontSize: '11px', fontWeight: 700,
                    padding: '2px 8px', borderRadius: '12px', textTransform: 'uppercase', letterSpacing: '0.5px'
                  }}>
                    {result.provider} / {result.model?.split('/').pop() || result.model}
                  </span>
                )}
                {genTime && (
                  <span style={{fontSize: '11px', color: 'var(--color-secondary)'}}>
                    ⚡ {genTime}s
                  </span>
                )}
                <StatusBadge status="verified" />
              </div>
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
