import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api/client';
import ComplianceCard from '../components/ComplianceCard';
import ForensicReport from '../components/ForensicReport';

export default function PublicVerifyPage() {
  const { runId } = useParams();
  const [assetInfo, setAssetInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [dragOver, setDragOver] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [droppedFileName, setDroppedFileName] = useState('');

  const [copiedHash, setCopiedHash] = useState(false);

  useEffect(() => {
    loadPublicAssetInfo();
  }, [runId]);

  const loadPublicAssetInfo = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/public/verify/${runId}`);
      setAssetInfo(res.data);
    } catch (err) {
      console.error(err);
      setError('Public verification record not found for this run ID.');
    } finally {
      setLoading(false);
    }
  };

  // Web Crypto API SHA-256 calculation on client side
  const computeSHA256 = async (file) => {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
    return hashHex;
  };

  const handleFileDrop = async (file) => {
    if (!file) return;
    setDroppedFileName(file.name);
    setVerifying(true);
    setVerifyResult(null);

    try {
      const fileHash = await computeSHA256(file);
      const formData = new FormData();
      formData.append('file_hash', fileHash);
      formData.append('file', file);
      const res = await api.post(`/public/verify/${runId}/file`, formData);
      setVerifyResult(res.data);
    } catch (err) {
      console.error(err);
      alert('Verification request failed.');
    } finally {
      setVerifying(false);
    }
  };

  const onDragOverHandler = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const onDragLeaveHandler = (e) => {
    e.preventDefault();
    setDragOver(false);
  };

  const onDropHandler = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileDrop(e.dataTransfer.files[0]);
    }
  };

  const onFileChangeHandler = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileDrop(e.target.files[0]);
    }
  };

  const triggerMockTamperTest = async () => {
    setDroppedFileName('modified_sample_asset.png');
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await api.post(`/public/verify/${runId}`, {
        file_hash: '1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff',
      });
      setVerifyResult(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setVerifying(false);
    }
  };

  const copyHash = () => {
    if (assetInfo?.sha256) {
      navigator.clipboard.writeText(assetInfo.sha256);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  return (
    <div className="public-verify-page">
      <div className="public-verify-topbar">
        <Link to="/" className="public-verify-brand">
          <div className="navbar-brand-icon">🛡️</div>
          <span>NOTARY PUBLIC PROVENANCE PORTAL</span>
        </Link>
        <Link to="/" className="btn btn-secondary btn-sm">
          ← Open App Dashboard
        </Link>
      </div>

      <div className="public-verify-container">
        <div className="public-verify-header">
          <div className="certificate-badge">
            <span className="certificate-badge-icon">📜</span>
            <span>PUBLIC PROVENANCE CERTIFICATE</span>
          </div>
          <h1>Independent Asset Audit Certificate</h1>
          <p>
            Cryptographically anchored to Backblaze B2 Object Lock. Verifiable origin and tamper protection.
          </p>
        </div>

        {loading ? (
          <div className="loading-overlay">
            <div className="spinner" />
            <span>Fetching public provenance record from B2 Object Lock...</span>
          </div>
        ) : error ? (
          <div className="verify-result fail">
            <span className="verify-result-icon">❌</span>
            <div className="verify-result-content">
              <h3>Record Not Found</h3>
              <p>{error}</p>
            </div>
          </div>
        ) : (
          <div className="public-verify-body">
            {/* Provenance Certificate Card */}
            <div className="provenance-card">
              <div className="provenance-card-header">
                <h2>🏛️ Official Provenance Record</h2>
                <span className="badge badge-verified">✓ Immutable Record</span>
              </div>

              <div className="provenance-grid">
                <div className="provenance-item">
                  <div className="provenance-label">Run Identifier</div>
                  <div className="provenance-value font-mono">{assetInfo.run_id}</div>
                </div>

                <div className="provenance-item">
                  <div className="provenance-label">AI Provider</div>
                  <div className="provenance-value">{assetInfo.provider}</div>
                </div>

                <div className="provenance-item">
                  <div className="provenance-label">Model Identifier</div>
                  <div className="provenance-value font-mono">{assetInfo.model}</div>
                </div>

                <div className="provenance-item">
                  <div className="provenance-label">Creation Timestamp</div>
                  <div className="provenance-value">
                    {new Date(assetInfo.created_at).toUTCString()}
                  </div>
                </div>

                <div className="provenance-item full-width">
                  <div className="provenance-label">Original Prompt</div>
                  <div className="provenance-value prompt-box">{assetInfo.prompt}</div>
                </div>

                <div className="provenance-item full-width">
                  <div className="provenance-label flex justify-between items-center">
                    <span>Canonical SHA-256 Hash</span>
                    <button className="btn btn-ghost btn-sm py-0 text-xs" onClick={copyHash}>
                      {copiedHash ? '✓ Copied!' : '📋 Copy Hash'}
                    </button>
                  </div>
                  <div className="provenance-value hash-box">{assetInfo.sha256}</div>
                </div>
              </div>
            </div>

            {/* Drag & Drop File Integrity Check */}
            <div className="provenance-card mt-6">
              <div className="provenance-card-header">
                <h2>🔍 File Integrity & Audit Check</h2>
                <span className="text-xs text-secondary font-mono">Web Crypto API</span>
              </div>
              <p className="text-sm text-secondary mb-4">
                Drag & drop a local media file to compute its cryptographic hash directly in your browser and verify authenticity.
              </p>

              <div
                className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
                onDragOver={onDragOverHandler}
                onDragLeave={onDragLeaveHandler}
                onDrop={onDropHandler}
                onClick={() => document.getElementById('fileInput').click()}
              >
                <input
                  type="file"
                  id="fileInput"
                  style={{ display: 'none' }}
                  onChange={onFileChangeHandler}
                />
                <div className="drop-zone-icon">📥</div>
                <div className="drop-zone-text">
                  {droppedFileName ? (
                    <strong className="text-primary">Selected: {droppedFileName}</strong>
                  ) : (
                    'Click or drag & drop a file here to run audit'
                  )}
                </div>
                <div className="drop-zone-hint">
                  Hash is computed in-browser; file bytes are sent only for forensic mismatch analysis
                </div>
              </div>

              <div className="mt-3 flex justify-end">
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={triggerMockTamperTest}
                >
                  🧪 Test Tamper Detection (Simulate Mismatch)
                </button>
              </div>

              {verifying && (
                <div className="loading-overlay my-4">
                  <div className="spinner" />
                  <span>Computing SHA-256 hash & running forensic analysis...</span>
                </div>
              )}

              {verifyResult && (
                <div
                  className={`verify-result mt-4 ${
                    verifyResult.match ? 'pass' : 'fail'
                  }`}
                >
                  <span className="verify-result-icon">
                    {verifyResult.match ? '✅' : '❌'}
                  </span>
                  <div className="verify-result-content">
                    <h3>
                      {verifyResult.match
                        ? 'AUTHENTIC FILE — 100% Hash Match'
                        : 'TAMPER DETECTED — Cryptographic Mismatch'}
                    </h3>
                    <p>Computed: {verifyResult.computed_hash}</p>
                    <p>Manifest: {verifyResult.manifest_hash}</p>
                  </div>
                </div>
              )}

              {verifyResult && verifyResult.forensic_analysis && (
                <ForensicReport forensic={verifyResult.forensic_analysis} />
              )}
            </div>

            {/* Compliance Scorecard */}
            {assetInfo.compliance_report && (
              <div className="mt-6">
                <div className="mb-4">
                  <h2 className="text-xl font-bold mb-1">
                    🏛️ Public Regulatory Compliance Scorecard
                  </h2>
                  <p className="text-xs text-secondary">
                    Compliance evaluation against international AI transparency mandates.
                  </p>
                </div>
                {assetInfo.compliance_report.regulations.map((reg) => (
                  <ComplianceCard key={reg.regulation_id} regulation={reg} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
