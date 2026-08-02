import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import api from '../api/client';
import StatusBadge from '../components/StatusBadge';
import ManifestPanel from '../components/ManifestPanel';
import ComplianceCard from '../components/ComplianceCard';
import ForensicReport from '../components/ForensicReport';
import LineageGraph from '../components/LineageGraph';

export default function AssetPage() {
  const { runId } = useParams();
  const navigate = useNavigate();

  const [asset, setAsset] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);

  const [showRemix, setShowRemix] = useState(false);
  const [remixPrompt, setRemixPrompt] = useState('');
  const [remixing, setRemixing] = useState(false);

  const [showBadge, setShowBadge] = useState(false);
  const [toast, setToast] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [assetRes, complianceRes] = await Promise.all([
        api.get(`/assets/${runId}`),
        api.get(`/assets/${runId}/compliance`),
      ]);
      setAsset(assetRes.data);
      setCompliance(complianceRes.data);
      setRemixPrompt(assetRes.data.prompt);
    } catch (err) {
      console.error(err);
      setError('Failed to load asset details.');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await api.post(`/assets/${runId}/verify`);
      setVerifyResult(res.data);
    } catch (err) {
      console.error(err);
      showToast('Verification failed to execute', 'error');
    } finally {
      setVerifying(false);
    }
  };

  const handleRemix = async (e) => {
    e.preventDefault();
    if (!remixPrompt.trim()) return;

    setRemixing(true);
    try {
      const res = await api.post(`/assets/${runId}/remix`, {
        prompt: remixPrompt,
      });
      setShowRemix(false);
      navigate(`/assets/${res.data.run_id}`);
    } catch (err) {
      console.error(err);
      showToast('Remix failed to generate', 'error');
    } finally {
      setRemixing(false);
    }
  };

  const handleShare = () => {
    const publicUrl = `${window.location.origin}/verify/${runId}`;
    navigator.clipboard.writeText(publicUrl);
    showToast('Public Verification URL copied to clipboard!', 'success');
  };

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  if (loading) {
    return (
      <div className="page">
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Loading asset details & manifest...</span>
        </div>
      </div>
    );
  }

  if (error || !asset) {
    return (
      <div className="page">
        <div className="verify-result fail">
          <span className="verify-result-icon">❌</span>
          <div className="verify-result-content">
            <h3>Asset Not Found</h3>
            <p>{error || 'The requested run ID does not exist.'}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header flex justify-between items-center flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-muted font-mono">Run ID: {asset.run_id}</span>
            {asset.parent_run_id && (
              <Link to={`/assets/${asset.parent_run_id}`} className="text-xs text-accent hover:underline">
                ↳ Parent: {asset.parent_run_id.slice(0, 8)}...
              </Link>
            )}
          </div>
          <h1 className="page-title">{asset.prompt}</h1>
          <div className="flex items-center gap-3 mt-2">
            <StatusBadge status={asset.modality} type="modality" />
            <span className="text-xs text-secondary">
              Created {new Date(asset.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        <div className="asset-actions">
          <button className="btn btn-primary" onClick={handleVerify} disabled={verifying}>
            {verifying ? <div className="spinner" /> : '🔍 Re-Verify Provenance'}
          </button>
          <button className="btn btn-secondary" onClick={() => setShowRemix(true)}>
            🔄 Remix Asset
          </button>
          <button className="btn btn-secondary" onClick={handleShare}>
            🔗 Copy Public Portal Link
          </button>
          <button className="btn btn-secondary" onClick={() => setShowBadge(true)}>
            🛡️ Embed Badge
          </button>
          <a
            className="btn btn-secondary"
            href={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/assets/${runId}/certificate`}
            target="_blank"
            rel="noopener noreferrer"
          >
            📜 Download Certificate
          </a>
        </div>
      </div>

      <div className="split-layout">
        {/* Left Column: Media Preview + Verification Result */}
        <div>
          <div className="asset-preview">
            {asset.modality === 'video' ? (
              <video controls autoPlay loop playsInline key={asset.run_id}>
                <source src={asset.b2_asset_url} type="video/mp4" />
                Your browser does not support video playback.
              </video>
            ) : (
              <img
                src={asset.b2_asset_url}
                alt={asset.prompt}
              />
            )}
          </div>

          {verifyResult && (
            <div className={`verify-result ${verifyResult.match ? 'pass' : 'fail'}`}>
              <span className="verify-result-icon">
                {verifyResult.match ? '✅' : '❌'}
              </span>
              <div className="verify-result-content">
                <h3>
                  {verifyResult.match
                    ? 'Cryptographic Verification PASSED'
                    : 'Cryptographic Verification FAILED'}
                </h3>
                <p>Computed: {verifyResult.computed_hash.slice(0, 24)}...</p>
                <p>Manifest: {verifyResult.manifest_hash.slice(0, 24)}...</p>
              </div>
            </div>
          )}

          {verifyResult && verifyResult.forensic_analysis && (
            <ForensicReport forensic={verifyResult.forensic_analysis} />
          )}

          <div className="mt-6">
            <ManifestPanel asset={asset} />
          </div>
        </div>

        {/* Right Column: Regulatory Compliance Scorecard (USP #1) */}
        <div>
          <div className="mb-4">
            <h2 className="text-xl font-bold mb-1">
              🏛️ Regulatory Compliance Scorecard
            </h2>
            <p className="text-xs text-secondary">
              Automated evaluation against global AI transparency mandates.
            </p>
          </div>

          {compliance ? (
            <div>
              {compliance.regulations.map((reg) => (
                <ComplianceCard key={reg.regulation_id} regulation={reg} />
              ))}

              {compliance.recommendations && compliance.recommendations.length > 0 && (
                <div className="compliance-recommendations card mt-4">
                  <h4>💡 Actionable Recommendations</h4>
                  <ul>
                    {compliance.recommendations.map((rec, idx) => (
                      <li key={idx}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="text-secondary text-sm">
              Loading compliance report...
            </div>
          )}
        </div>
      </div>

      {/* Lineage DAG */}
      <div style={{ marginTop: 24 }}>
        <LineageGraph runId={runId} />
      </div>

      {/* Remix Modal */}
      {showRemix && (
        <div className="modal-overlay" onClick={() => setShowRemix(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Remix Asset (Version Lineage)</h2>
            <p className="text-xs text-secondary mb-4">
              Create a new derivative generation. The parent run ID ({runId.slice(0, 8)}...) will be cryptographically linked in the manifest.
            </p>
            <form onSubmit={handleRemix}>
              <div className="input-group mb-4">
                <label className="input-label">Modified Prompt</label>
                <textarea
                  className="textarea"
                  value={remixPrompt}
                  onChange={(e) => setRemixPrompt(e.target.value)}
                  required
                />
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowRemix(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={remixing}
                >
                  {remixing ? <div className="spinner" /> : 'Generate Remix'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          {toast.message}
        </div>
      )}

      {/* Badge Embed Modal */}
      {showBadge && (
        <div className="modal-overlay" onClick={() => setShowBadge(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>🛡️ Embed Provenance Badge</h2>
            <p className="text-xs text-secondary mb-4">
              Embed this badge on any webpage to show the live verification status of this asset.
            </p>
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <img
                src={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/badge/${runId}`}
                alt="Notary Provenance Badge"
                style={{ height: 22 }}
              />
            </div>
            <div className="input-group mb-4">
              <label className="input-label">HTML Embed Code</label>
              <textarea
                className="textarea"
                readOnly
                rows={3}
                value={`<a href="${window.location.origin}/verify/${runId}">\n  <img src="${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/badge/${runId}" alt="Verified by Notary" />\n</a>`}
                onClick={e => e.target.select()}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowBadge(false)}>Close</button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  const code = `<a href="${window.location.origin}/verify/${runId}">\n  <img src="${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/badge/${runId}" alt="Verified by Notary" />\n</a>`;
                  navigator.clipboard.writeText(code);
                  showToast('Badge embed code copied!', 'success');
                  setShowBadge(false);
                }}
              >
                📋 Copy Embed Code
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
