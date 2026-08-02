import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import StatusBadge from '../components/StatusBadge';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function GeneratePage() {
  const [prompt, setPrompt] = useState('');
  const [modality, setModality] = useState('image');
  const [policyProfile, setPolicyProfile] = useState('general');
  const [policyReview, setPolicyReview] = useState(null);
  const [policyAcknowledged, setPolicyAcknowledged] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [genTime, setGenTime] = useState(null);
  const [cascadeLog, setCascadeLog] = useState([]);
  const navigate = useNavigate();

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    setError(null);
    try {
      const reviewResponse = await fetch(`${BASE_URL}/policy/prompt-review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, policy_profile: policyProfile }),
      });
      const review = await reviewResponse.json();
      if (!reviewResponse.ok) throw new Error(review.detail || 'Policy review failed.');
      setPolicyReview(review);
      if (review.status === 'block') {
        setError('This prompt is blocked by the selected policy profile.');
        return;
      }
      if (review.requires_acknowledgement && !policyAcknowledged) {
        return;
      }
    } catch (err) {
      setError(err.message || 'Policy review failed.');
      return;
    }

    setLoading(true);
    setResult(null);
    setGenTime(null);
    setCascadeLog([]);
    const t0 = performance.now();

    try {
      // Use SSE streaming endpoint for real-time cascade visibility
      const response = await fetch(`${BASE_URL}/generate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          modality,
          policy_profile: policyProfile,
          policy_acknowledged: policyAcknowledged,
        }),
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
              } else if (event.stage === 'policy_blocked') {
                setPolicyReview(event.policy_audit || null);
                setError(event.message);
              }
            } catch {
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
              onChange={(e) => {
                setPrompt(e.target.value);
                setPolicyReview(null);
                setPolicyAcknowledged(false);
              }}
              required
            />
          </div>

          <div className="input-group mb-6">
            <label className="input-label" htmlFor="policy-profile">Policy profile</label>
            <select
              id="policy-profile"
              className="input"
              value={policyProfile}
              onChange={(e) => {
                setPolicyProfile(e.target.value);
                setPolicyReview(null);
                setPolicyAcknowledged(false);
              }}
            >
              <option value="general">General generation</option>
              <option value="public-release">Public release review</option>
              <option value="brand-safe">Brand-safe review</option>
            </select>
          </div>

          {policyReview && (
            <div className={`verify-result ${policyReview.status === 'block' ? 'fail' : policyReview.status === 'warning' ? 'partial' : 'pass'} mb-6`}>
              <span className="verify-result-icon">
                {policyReview.status === 'pass' ? '✓' : policyReview.status === 'warning' ? '!' : '×'}
              </span>
              <div className="verify-result-content">
                <h3>Prompt policy review: {policyReview.status}</h3>
                {policyReview.findings?.map((finding) => (
                  <p key={finding.rule_id}><strong>{finding.rule_id}</strong> {finding.detail} {finding.suggestion}</p>
                ))}
                {policyReview.requires_acknowledgement && !policyAcknowledged && (
                  <label className="text-sm" style={{ display: 'block', marginTop: 10 }}>
                    <input
                      type="checkbox"
                      checked={policyAcknowledged}
                      onChange={(e) => setPolicyAcknowledged(e.target.checked)}
                    />{' '}
                    I reviewed this warning and want the audit recorded with the asset.
                  </label>
                )}
              </div>
            </div>
          )}

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
                <span>{policyReview?.requires_acknowledgement && !policyAcknowledged ? 'Acknowledge Warning to Continue' : 'Generate & Lock Provenance'}</span>
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
              const icon = ev.stage === 'cache_hit' ? '⚡'
                : ev.stage.includes('success') || ev.stage === 'completed' ? '✅'
                : ev.stage.includes('error') || ev.stage.includes('exhausted') || ev.stage === 'failed' ? '❌'
                : ev.stage.includes('trying') ? '🔄'
                : ev.stage.includes('quota') ? '⚠️' : '•';
              const color = ev.stage === 'cache_hit' ? '#f59e0b'
                : ev.stage.includes('success') || ev.stage === 'completed' ? '#2ea44f'
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
                <StatusBadge status="unknown" />
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
                Your browser does not support video playback.
              </video>
            ) : (
              <img
                src={result.asset_url}
                alt="Generated output"
                className="generate-result-image"
              />
            )}

            <div className="generate-result-meta">
              {result.policy_audit && (
                <div className="mb-4 text-sm">
                  <strong>Policy audit:</strong> prompt {result.policy_audit.prompt_audit.status}; visual {result.policy_audit.visual_audit?.status || 'unavailable'}
                </div>
              )}
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
