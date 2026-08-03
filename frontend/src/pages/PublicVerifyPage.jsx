import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Shield,
  FileCheck,
  FileText,
  Copy,
  Search,
  UploadCloud,
  CheckCircle2,
  XCircle,
  Scale,
  ArrowLeft,
  Check,
} from 'lucide-react';
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

  const loadPublicAssetInfo = useCallback(async () => {
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
  }, [runId]);

  useEffect(() => {
    loadPublicAssetInfo();
  }, [loadPublicAssetInfo]);

  // Web Crypto API SHA-256 calculation on client side
  const computeSHA256 = async (file) => {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
    return hashHex;
  };

  const [dropError, setDropError] = useState('');

  const handleFileDrop = async (file) => {
    if (!file) return;
    setDroppedFileName(file.name);
    setVerifying(true);
    setVerifyResult(null);
    setDropError('');

    try {
      const fileHash = await computeSHA256(file);
      const formData = new FormData();
      formData.append('file_hash', fileHash);
      formData.append('file', file);
      const res = await api.post(`/public/verify/${runId}/file`, formData);
      setVerifyResult(res.data);
    } catch (err) {
      console.error(err);
      setDropError(err.response?.data?.detail || 'Verification request failed. Please try again.');
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
          <div className="navbar-brand-icon">
            <Shield style={{ width: 18, height: 18 }} />
          </div>
          <span>NOTARY PUBLIC PROVENANCE PORTAL</span>
        </Link>
        <Link to="/" className="btn btn-secondary btn-sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <ArrowLeft style={{ width: 14, height: 14 }} />
          <span>Open App Dashboard</span>
        </Link>
      </div>

      <div className="public-verify-container">
        <div className="public-verify-header">
          <div className="certificate-badge">
            <FileCheck style={{ width: 14, height: 14 }} />
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
            <XCircle style={{ width: 24, height: 24, color: '#ff2047', flexShrink: 0 }} />
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
                <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FileText style={{ width: 20, height: 20, color: '#3b9eff' }} />
                  <span>Official Provenance Record</span>
                </h2>
                <span className="badge badge-verified" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <Check style={{ width: 12, height: 12 }} />
                  <span>Immutable Record</span>
                </span>
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
                    <button className="btn btn-ghost btn-sm py-0 text-xs" onClick={copyHash} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      {copiedHash ? (
                        <>
                          <Check style={{ width: 12, height: 12 }} />
                          <span>Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy style={{ width: 12, height: 12 }} />
                          <span>Copy Hash</span>
                        </>
                      )}
                    </button>
                  </div>
                  <div className="provenance-value hash-box">{assetInfo.sha256}</div>
                </div>
              </div>
            </div>

            {/* Drag & Drop File Integrity Check */}
            <div className="provenance-card mt-6">
              <div className="provenance-card-header">
                <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Search style={{ width: 20, height: 20, color: '#3b9eff' }} />
                  <span>File Integrity & Audit Check</span>
                </h2>
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
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <UploadCloud style={{ width: 36, height: 36, opacity: 0.5, marginBottom: 8 }} />
                </div>
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

              {verifying && (
                <div className="loading-overlay my-4">
                  <div className="spinner" />
                  <span>Computing SHA-256 hash & running forensic analysis...</span>
                </div>
              )}

              {dropError && (
                <div className="verify-result fail mt-4">
                  <XCircle style={{ width: 24, height: 24, color: '#ff2047', flexShrink: 0 }} />
                  <div className="verify-result-content">
                    <h3>Verification Error</h3>
                    <p>{dropError}</p>
                  </div>
                </div>
              )}

              {verifyResult && (
                <div
                  className={`verify-result mt-4 ${
                    verifyResult.match ? 'pass' : 'fail'
                  }`}
                >
                  {verifyResult.match ? (
                    <CheckCircle2 style={{ width: 24, height: 24, color: '#11ff99', flexShrink: 0 }} />
                  ) : (
                    <XCircle style={{ width: 24, height: 24, color: '#ff2047', flexShrink: 0 }} />
                  )}
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
                  <h2 className="text-xl font-bold mb-1" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Scale style={{ width: 22, height: 22, color: '#3b9eff' }} />
                    <span>Public Regulatory Compliance Scorecard</span>
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
