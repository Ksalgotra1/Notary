import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Image as ImageIcon, Video as VideoIcon, Sparkles, CheckCircle2, XCircle, AlertTriangle, RotateCw, Layers, Key, ChevronDown, ExternalLink, Eye, EyeOff, Trash2 } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import SmartAssetImage from '../components/SmartAssetImage';

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

  // ... (rest of state stays same)
  // Let's replace lines 125-147 in render:

  const [genTime, setGenTime] = useState(null);
  const [cascadeLog, setCascadeLog] = useState([]);
  const navigate = useNavigate();

  // ── BYOK state ────────────────────────────────────────────────────
  const [byokExpanded, setByokExpanded] = useState(false);
  const [userGoogleKey, setUserGoogleKey] = useState(() => sessionStorage.getItem('byok_google') || '');
  const [userNvidiaKey, setUserNvidiaKey] = useState(() => sessionStorage.getItem('byok_nvidia') || '');
  const [showGoogleKey, setShowGoogleKey] = useState(false);
  const [showNvidiaKey, setShowNvidiaKey] = useState(false);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    fetch(`${BASE_URL}/health`).then(r => r.json()).then(setHealth).catch(() => {});
  }, []);

  const handleGoogleKeyChange = (val) => {
    setUserGoogleKey(val);
    if (val) sessionStorage.setItem('byok_google', val);
    else sessionStorage.removeItem('byok_google');
  };
  const handleNvidiaKeyChange = (val) => {
    setUserNvidiaKey(val);
    if (val) sessionStorage.setItem('byok_nvidia', val);
    else sessionStorage.removeItem('byok_nvidia');
  };
  const clearAllKeys = () => {
    setUserGoogleKey('');
    setUserNvidiaKey('');
    sessionStorage.removeItem('byok_google');
    sessionStorage.removeItem('byok_nvidia');
  };

  const hasUserKeys = userGoogleKey.trim() || userNvidiaKey.trim();
  // ── End BYOK state ────────────────────────────────────────────────

  const THINKING_WORDS = [
    'Notarizing', 'Hashing', 'Sealing', 'Contemplating',
    'Triangulating', 'Crystallizing', 'Authenticating', 'Forging',
    'Minting', 'Inscribing', 'Certifying', 'Etching',
    'Encoding', 'Anchoring', 'Commissioning', 'Orchestrating',
  ];

  const [thinkingIdx, setThinkingIdx] = useState(0);

  useEffect(() => {
    if (!loading) return;
    setThinkingIdx(0);
    const interval = setInterval(() => {
      setThinkingIdx(prev => (prev + 1) % THINKING_WORDS.length);
    }, 2000);
    return () => clearInterval(interval);
  }, [loading]);

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
          // BYOK: send user keys per-request; never stored server-side
          ...(userGoogleKey.trim() ? { google_api_key: userGoogleKey.trim() } : {}),
          ...(userNvidiaKey.trim() ? { nvidia_api_key: userNvidiaKey.trim() } : {}),
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
                style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              >
                <ImageIcon style={{ width: 15, height: 15 }} />
                <span>Image (Imagen)</span>
              </button>
              <button
                type="button"
                className={`modality-option ${
                  modality === 'video' ? 'active' : ''
                }`}
                onClick={() => setModality('video')}
                style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              >
                <VideoIcon style={{ width: 15, height: 15 }} />
                <span>Video (Veo)</span>
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

          {/* ── BYOK: Bring Your Own Keys ──────────────────────────── */}
          <div className={`byok-panel ${byokExpanded ? 'expanded' : ''} mb-6`}>
            <button
              type="button"
              className="byok-header"
              onClick={() => setByokExpanded(p => !p)}
              aria-expanded={byokExpanded}
            >
              <span className="byok-header-left">
                <Key style={{ width: 14, height: 14 }} />
                <span>Bring Your Own API Keys</span>
                {hasUserKeys && <span className="byok-keys-active-dot" title="Custom keys active" />}
              </span>
              <ChevronDown
                style={{
                  width: 15, height: 15,
                  transition: 'transform 0.25s ease',
                  transform: byokExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                }}
              />
            </button>

            {byokExpanded && (
              <div className="byok-body">
                {/* Transparency block */}
                <div className="byok-transparency">
                  <p>
                    <strong>This is an early-stage, open-source student project.</strong> We don&apos;t
                    yet have production Google Gemini or NVIDIA API keys, so free-tier providers
                    (HuggingFace, Pollinations) are used by default — they may be slower or occasionally
                    unavailable.
                  </p>
                  <p style={{ marginTop: 8 }}>
                    If you have your own API keys, you can add them below. They&apos;re sent
                    in-memory per-request and <strong>never stored on any server,
                    database, or manifest</strong>.
                  </p>
                  <a
                    href="https://github.com/Ksalgotra1/notary"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="byok-github-link"
                  >
                    <ExternalLink style={{ width: 12, height: 12 }} />
                    Verify on GitHub — github.com/Ksalgotra1/notary
                  </a>
                </div>

                {/* Provider status row */}
                <div className="byok-provider-status">
                  {[
                    {
                      label: 'Google Gemini',
                      active: health ? health.google_keys_configured > 0 || userGoogleKey.trim() : !!userGoogleKey.trim(),
                      note: userGoogleKey.trim() ? 'your key' : health?.google_keys_configured > 0 ? 'server key' : 'no key',
                    },
                    {
                      label: 'NVIDIA',
                      active: health ? health.nvidia_key_configured || !!userNvidiaKey.trim() : !!userNvidiaKey.trim(),
                      note: userNvidiaKey.trim() ? 'your key' : health?.nvidia_key_configured ? 'server key' : 'no key',
                    },
                    {
                      label: 'HuggingFace',
                      active: true,
                      note: 'free tier',
                    },
                    {
                      label: 'Pollinations',
                      active: true,
                      note: 'free tier',
                    },
                  ].map(p => (
                    <div key={p.label} className="byok-provider-chip">
                      <span className={`byok-status-dot ${p.active ? 'active' : 'inactive'}`} />
                      <span className="byok-provider-label">{p.label}</span>
                      <span className="byok-provider-note">{p.note}</span>
                    </div>
                  ))}
                </div>

                {/* Key inputs */}
                <div className="byok-inputs">
                  <div className="byok-input-group">
                    <label className="byok-input-label">Google Gemini API Key</label>
                    <div className="byok-input-wrapper">
                      <input
                        type={showGoogleKey ? 'text' : 'password'}
                        className="byok-input"
                        placeholder="AIza..."
                        value={userGoogleKey}
                        onChange={e => handleGoogleKeyChange(e.target.value)}
                        autoComplete="off"
                        spellCheck={false}
                      />
                      <button
                        type="button"
                        className="byok-toggle-btn"
                        onClick={() => setShowGoogleKey(p => !p)}
                        title={showGoogleKey ? 'Hide key' : 'Show key'}
                      >
                        {showGoogleKey
                          ? <EyeOff style={{ width: 13, height: 13 }} />
                          : <Eye style={{ width: 13, height: 13 }} />}
                      </button>
                    </div>
                    <span className="byok-input-hint">From <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer">Google AI Studio</a> — enables Imagen &amp; Veo</span>
                  </div>

                  <div className="byok-input-group">
                    <label className="byok-input-label">NVIDIA API Key</label>
                    <div className="byok-input-wrapper">
                      <input
                        type={showNvidiaKey ? 'text' : 'password'}
                        className="byok-input"
                        placeholder="nvapi-..."
                        value={userNvidiaKey}
                        onChange={e => handleNvidiaKeyChange(e.target.value)}
                        autoComplete="off"
                        spellCheck={false}
                      />
                      <button
                        type="button"
                        className="byok-toggle-btn"
                        onClick={() => setShowNvidiaKey(p => !p)}
                        title={showNvidiaKey ? 'Hide key' : 'Show key'}
                      >
                        {showNvidiaKey
                          ? <EyeOff style={{ width: 13, height: 13 }} />
                          : <Eye style={{ width: 13, height: 13 }} />}
                      </button>
                    </div>
                    <span className="byok-input-hint">From <a href="https://build.nvidia.com" target="_blank" rel="noopener noreferrer">NVIDIA Build</a> — enables FLUX</span>
                  </div>
                </div>

                {hasUserKeys && (
                  <button type="button" className="byok-clear-btn" onClick={clearAllKeys}>
                    <Trash2 style={{ width: 12, height: 12 }} />
                    Clear saved keys
                  </button>
                )}
              </div>
            )}
          </div>
          {/* ── End BYOK ─────────────────────────────────────────── */}

          {policyReview && (
            <div
              className={`verify-result ${
                policyReview.status === 'block'
                  ? 'fail'
                  : policyReview.status === 'warning'
                  ? 'partial'
                  : 'pass'
              } mb-6`}
            >
              {policyReview.status === 'pass' ? (
                <CheckCircle2 style={{ width: 22, height: 22, color: '#11ff99', flexShrink: 0 }} />
              ) : policyReview.status === 'warning' ? (
                <AlertTriangle style={{ width: 22, height: 22, color: '#ffc53d', flexShrink: 0 }} />
              ) : (
                <XCircle style={{ width: 22, height: 22, color: '#ff2047', flexShrink: 0 }} />
              )}
              <div className="verify-result-content">
                <h3 style={{ fontSize: '0.9375rem', textTransform: 'capitalize' }}>
                  Prompt policy review: {policyReview.status}
                </h3>
                {policyReview.findings?.map((finding) => (
                  <p key={finding.rule_id} style={{ fontSize: '0.8125rem', marginTop: 4, color: 'var(--text-primary)' }}>
                    <strong style={{ color: '#fcfdff' }}>{finding.rule_id}:</strong> {finding.detail} {finding.suggestion}
                  </p>
                ))}
                {policyReview.requires_acknowledgement && !policyAcknowledged && (
                  <label className="text-sm" style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, cursor: 'pointer', color: '#ffc53d' }}>
                    <input
                      type="checkbox"
                      checked={policyAcknowledged}
                      onChange={(e) => setPolicyAcknowledged(e.target.checked)}
                    />
                    <span>I reviewed this warning and want the audit recorded with the asset.</span>
                  </label>
                )}
              </div>
            </div>
          )}

          <div className="form-actions text-center mt-6">
            <button
              type="submit"
              className="btn btn-primary btn-lg btn-generate"
              disabled={loading || !prompt.trim()}
            >
              {loading ? (
                <>
                  <div className="spinner" />
                  <span
                    key={thinkingIdx}
                    style={{
                      display: 'inline-block',
                      animation: 'thinkingFadeIn 0.4s ease',
                    }}
                  >
                    {THINKING_WORDS[thinkingIdx]}...
                  </span>
                </>
              ) : (
                <>
                  <span>{policyReview?.requires_acknowledgement && !policyAcknowledged ? 'Acknowledge Warning to Continue' : 'Generate & Lock Provenance'}</span>
                </>
              )}
            </button>
          </div>
        </form>

        {error && (
          <div className="verify-result fail mt-6" style={{ background: 'rgba(255, 32, 71, 0.08)', border: '1px solid rgba(255, 32, 71, 0.3)', padding: 20 }}>
            <XCircle style={{ width: 24, height: 24, color: '#ff5c77', flexShrink: 0 }} />
            <div className="verify-result-content">
              <h3 style={{ color: '#ff5c77', fontSize: '1rem', fontWeight: 600 }}>Generation Error</h3>
              <p style={{ color: '#fcfdff', fontSize: '0.875rem', marginTop: 6, lineHeight: 1.6 }}>
                {error}
              </p>
            </div>
          </div>
        )}

        {/* Live Cascade Log Terminal */}
        {cascadeLog.length > 0 && (
          <div
            style={{
              marginTop: 20,
              background: '#06060a',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-lg)',
              padding: '18px 20px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8125rem',
              maxHeight: 240,
              overflowY: 'auto',
            }}
          >
            <div
              style={{
                fontSize: '0.75rem',
                color: '#3b9eff',
                marginBottom: 12,
                fontFamily: 'var(--font-heading)',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}
            >
              <Layers style={{ width: 14, height: 14 }} />
              <span>Provider Cascade Log</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {cascadeLog.map((ev, i) => {
                const isSuccess = ev.stage.includes('success') || ev.stage === 'completed' || ev.stage === 'cache_hit';
                const isError = ev.stage.includes('error') || ev.stage.includes('exhausted') || ev.stage === 'failed';
                const isTrying = ev.stage.includes('trying') || ev.stage.includes('started');
                const isQuota = ev.stage.includes('quota') || ev.stage.includes('warning');

                const textColor = isSuccess ? '#11ff99' : isError ? '#ff5c77' : isTrying ? '#70baff' : isQuota ? '#ffc53d' : '#fcfdff';

                return (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      lineHeight: 1.5,
                    }}
                  >
                    <span style={{ flexShrink: 0, marginTop: 2 }}>
                      {isSuccess ? (
                        <CheckCircle2 style={{ width: 14, height: 14, color: '#11ff99' }} />
                      ) : isError ? (
                        <XCircle style={{ width: 14, height: 14, color: '#ff5c77' }} />
                      ) : isTrying ? (
                        <RotateCw style={{ width: 14, height: 14, color: '#70baff' }} />
                      ) : isQuota ? (
                        <AlertTriangle style={{ width: 14, height: 14, color: '#ffc53d' }} />
                      ) : (
                        <span style={{ color: '#a1a4a5' }}>•</span>
                      )}
                    </span>

                    <span style={{ color: '#a1a4a5', minWidth: 65, flexShrink: 0, fontFamily: 'var(--font-mono)' }}>
                      {ev.elapsed_ms}ms
                    </span>

                    <span style={{ color: textColor, wordBreak: 'break-word', flex: 1, fontFamily: 'var(--font-body)' }}>
                      {ev.message}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {result && (
          <div className="generate-result border-t border-border pt-6 mt-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Generated Asset</h3>
              <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                {result.provider && (
                  <span style={{
                    background: result.provider === 'google' ? '#1a73e8' : result.provider === 'nvidia' ? '#76b900' : '#3b9eff',
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
              <SmartAssetImage
                src={result.asset_url}
                alt="Failed to generate asset image"
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
