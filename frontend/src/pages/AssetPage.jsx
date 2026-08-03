import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  RotateCw,
  Scissors,
  Link as LinkIcon,
  Code,
  Download,
  CheckCircle2,
  XCircle,
  Scale,
  Lightbulb,
  GitBranch,
} from 'lucide-react';
import api from '../api/client';
import ManifestPanel from '../components/ManifestPanel';
import ComplianceCard from '../components/ComplianceCard';
import ForensicReport from '../components/ForensicReport';
import LineageGraph from '../components/LineageGraph';
import SmartAssetImage from '../components/SmartAssetImage';

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

  useEffect(() => {
    setShowRemix(false);
    setRemixing(false);
    setVerifyResult(null);
  }, [runId]);

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
      const remixedRunId = res.data?.run_id;
      if (!remixedRunId) {
        throw new Error('Remix completed but the response did not include a run ID.');
      }
      setShowRemix(false);
      setRemixing(false);
      navigate(`/assets/${remixedRunId}`);
    } catch (err) {
      console.error(err);
      showToast(err.message || 'Remix failed to generate', 'error');
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
          <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            Loading asset details & manifest...
          </span>
        </div>
      </div>
    );
  }

  if (error || !asset) {
    return (
      <div className="page">
        <div className="verify-result fail">
          <XCircle style={{ width: 24, height: 24, color: '#ff2047', flexShrink: 0 }} />
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
      {/* Top Breadcrumb Nav */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: '0.8125rem',
          color: 'var(--text-secondary)',
          marginBottom: 16,
          flexWrap: 'wrap',
          fontFamily: 'var(--font-body)',
        }}
      >
        <Link to="/dashboard" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }} className="hover:underline">
          AI Asset Compliance & Provenance Dashboard
        </Link>
        <span>›</span>
        <Link to="/library" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }} className="hover:underline">
          AI Assets
        </Link>
        <span>›</span>
        <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{asset.prompt}</span>
      </div>

      {/* Header Metadata + Title + Action Bar */}
      <div style={{ marginBottom: 28 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            fontSize: '0.8125rem',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            marginBottom: 8,
            flexWrap: 'wrap',
          }}
        >
          <span>Run ID: {asset.run_id}</span>
          {asset.parent_run_id && (
            <Link to={`/assets/${asset.parent_run_id}`} style={{ color: 'var(--accent-blue)', textDecoration: 'none' }}>
              Parent: {asset.parent_run_id.slice(0, 10)}...
            </Link>
          )}
          <span>Created: {new Date(asset.created_at).toLocaleString()}</span>
        </div>

        <h1
          className="page-title"
          style={{
            fontSize: '2.5rem',
            fontWeight: 700,
            fontFamily: 'var(--font-heading)',
            color: 'var(--text-primary)',
            margin: '0 0 20px 0',
            lineHeight: 1.15,
          }}
        >
          {asset.prompt}
        </h1>

        {/* Action Buttons Row matching screenshot */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            className="btn btn-secondary"
            onClick={handleVerify}
            disabled={verifying}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            {verifying ? (
              <div className="spinner" />
            ) : (
              <>
                <RotateCw style={{ width: 14, height: 14 }} />
                <span>Re-Verify Provenance</span>
              </>
            )}
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => setShowRemix(true)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <Scissors style={{ width: 14, height: 14 }} />
            <span>Remix Asset</span>
          </button>

          <button
            className="btn btn-secondary"
            onClick={handleShare}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <LinkIcon style={{ width: 14, height: 14 }} />
            <span>Copy Public Portal Link</span>
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => setShowBadge(true)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <Code style={{ width: 14, height: 14 }} />
            <span>Embed Badge</span>
          </button>

          <a
            className="btn btn-secondary"
            href={`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/assets/${runId}/certificate`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}
          >
            <Download style={{ width: 14, height: 14 }} />
            <span>Download Certificate</span>
          </a>
        </div>
      </div>

      {/* Main Split Layout: Left Preview, Right Scorecard & Recommendations */}
      <div className="split-layout">
        {/* Left Column: Media Preview + Verification Result + Provenance Manifest */}
        <div>
          <div className="asset-preview card" style={{ padding: 16, overflow: 'hidden' }}>
            {asset.modality === 'video' ? (
              <video controls autoPlay loop playsInline key={asset.run_id} style={{ width: '100%', borderRadius: 8 }}>
                <source src={asset.b2_asset_url} type="video/mp4" />
                Your browser does not support video playback.
              </video>
            ) : (
              <SmartAssetImage
                src={asset.b2_asset_url}
                alt="Failed to generate asset image"
                style={{ borderRadius: 8, width: '100%', display: 'block', maxHeight: 500, objectFit: 'contain' }}
              />
            )}
          </div>

          {verifyResult && (
            <div className={`verify-result ${verifyResult.match ? 'pass' : 'fail'}`}>
              {verifyResult.match ? (
                <CheckCircle2 style={{ width: 24, height: 24, color: '#11ff99', flexShrink: 0 }} />
              ) : (
                <XCircle style={{ width: 24, height: 24, color: '#ff2047', flexShrink: 0 }} />
              )}
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

          <div style={{ marginTop: 24 }}>
            <ManifestPanel asset={asset} />
          </div>
        </div>

        {/* Right Column: Regulatory Compliance Scorecard & Recommendations */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Regulatory Compliance Scorecard Card */}
          <div className="card" style={{ padding: 24 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                marginBottom: 16,
              }}
            >
              <Scale style={{ width: 20, height: 20, color: '#3b9eff' }} />
              <h2 className="text-section" style={{ fontSize: '1.125rem', fontWeight: 600, margin: 0 }}>
                Regulatory Compliance Scorecard
              </h2>
            </div>

            {compliance ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {compliance.regulations.map((reg) => (
                  <ComplianceCard key={reg.regulation_id} regulation={reg} />
                ))}
              </div>
            ) : (
              <div className="text-secondary text-sm">Loading compliance report...</div>
            )}
          </div>

          {/* Actionable Recommendations Card */}
          {compliance && compliance.recommendations && compliance.recommendations.length > 0 && (
            <div className="card" style={{ padding: 24 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  marginBottom: 14,
                }}
              >
                <Lightbulb style={{ width: 18, height: 18, color: '#ffc53d' }} />
                <h2 className="text-section" style={{ fontSize: '1.125rem', fontWeight: 600, margin: 0 }}>
                  Actionable Recommendations
                </h2>
              </div>
              <ul style={{ paddingLeft: 20, margin: 0, color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: 1.6 }}>
                {compliance.recommendations.map((rec, idx) => (
                  <li key={idx} style={{ marginBottom: 6 }}>{rec}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Provenance Lineage Graph Card (Right Side of Provenance) */}
          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
              <GitBranch style={{ width: 20, height: 20, color: '#3b9eff' }} />
              <h2 className="text-section" style={{ fontSize: '1.125rem', fontWeight: 600, margin: 0 }}>
                Provenance Lineage Graph
              </h2>
            </div>
            <LineageGraph runId={runId} />
          </div>
        </div>
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
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Embed Provenance Badge</h2>
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
                onClick={(e) => e.target.select()}
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
                Copy Embed Code
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
