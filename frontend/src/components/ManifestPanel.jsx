import React, { useState } from 'react';
import { FileCode, Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';

export default function ManifestPanel({ asset }) {
  const [isOpen, setIsOpen] = useState(true);
  const [viewJson, setViewJson] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!asset) return null;

  const handleCopyJson = (e) => {
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.writeText(JSON.stringify(asset, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const rows = [
    { key: 'RUN ID', value: asset.run_id },
    ...(asset.parent_run_id ? [{ key: 'PARENT RUN ID', value: asset.parent_run_id }] : []),
    { key: 'PROVIDER', value: asset.provider },
    { key: 'MODEL', value: asset.model },
    { key: 'MODALITY', value: asset.modality },
    { key: 'PROMPT', value: asset.prompt },
    { key: 'SHA-256 HASH', value: asset.sha256 },
    { key: 'CREATED AT', value: asset.created_at },
    { key: 'B2 ASSET URL', value: asset.b2_asset_url },
    { key: 'B2 MANIFEST URI', value: asset.b2_manifest_url },
  ];

  return (
    <div className="manifest-panel card" style={{ padding: 0, overflow: 'hidden' }}>
      {/* Panel Header */}
      <div
        className="manifest-header"
        onClick={() => setIsOpen((prev) => !prev)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '18px 24px',
          cursor: 'pointer',
          userSelect: 'none',
          background: 'var(--bg-card)',
          borderBottom: isOpen ? '1px solid var(--border)' : 'none',
        }}
      >
        <h3
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            fontSize: '1rem',
            fontWeight: 600,
            fontFamily: 'var(--font-heading)',
            color: 'var(--text-primary)',
            margin: 0,
          }}
        >
          <FileCode style={{ width: 18, height: 18, color: '#3b9eff' }} />
          <span>Provenance Manifest</span>
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            style={{
              fontSize: '0.8125rem',
              color: 'var(--text-secondary)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {asset.run_id ? asset.run_id.slice(0, 8) + '...' : ''}
          </span>
          {isOpen ? (
            <ChevronUp style={{ width: 16, height: 16, color: 'var(--text-muted)' }} />
          ) : (
            <ChevronDown style={{ width: 16, height: 16, color: 'var(--text-muted)' }} />
          )}
        </div>
      </div>

      {/* Panel Body */}
      {isOpen && (
        <div className="manifest-body" style={{ padding: '24px' }}>
          {/* View Mode Switcher Tabs matching screenshot */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 24,
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div
              style={{
                display: 'inline-flex',
                gap: 6,
                background: 'rgba(255, 255, 255, 0.04)',
                padding: '4px',
                borderRadius: '8px',
                border: '1px solid var(--border)',
              }}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setViewJson(false);
                }}
                style={{
                  padding: '6px 16px',
                  fontSize: '0.8125rem',
                  fontWeight: !viewJson ? 600 : 500,
                  fontFamily: 'var(--font-body)',
                  borderRadius: '6px',
                  border: 'none',
                  cursor: 'pointer',
                  background: !viewJson ? '#ffffff' : 'transparent',
                  color: !viewJson ? '#000000' : 'rgba(252, 253, 255, 0.7)',
                  transition: 'all 150ms ease',
                }}
              >
                Structured View
              </button>

              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setViewJson(true);
                }}
                style={{
                  padding: '6px 16px',
                  fontSize: '0.8125rem',
                  fontWeight: viewJson ? 600 : 500,
                  fontFamily: 'var(--font-body)',
                  borderRadius: '6px',
                  border: 'none',
                  cursor: 'pointer',
                  background: viewJson ? '#ffffff' : 'transparent',
                  color: viewJson ? '#000000' : 'rgba(252, 253, 255, 0.7)',
                  transition: 'all 150ms ease',
                }}
              >
                Raw JSON
              </button>
            </div>

            {viewJson && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleCopyJson}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', height: 32 }}
              >
                {copied ? <Check style={{ width: 14, height: 14, color: '#11ff99' }} /> : <Copy style={{ width: 14, height: 14 }} />}
                <span>{copied ? 'Copied!' : 'Copy JSON'}</span>
              </button>
            )}
          </div>

          {/* Mode Content */}
          {viewJson ? (
            <pre
              className="manifest-json"
              style={{
                background: '#06060a',
                border: '1px solid var(--border-strong)',
                borderRadius: '8px',
                padding: '18px 20px',
                fontSize: '0.8125rem',
                fontFamily: 'var(--font-mono)',
                color: '#11ff99',
                maxHeight: 450,
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                lineHeight: 1.6,
              }}
            >
              {JSON.stringify(asset, null, 2)}
            </pre>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {rows.map((row, idx) => (
                <div
                  key={row.key}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(140px, 200px) 1fr',
                    gap: 16,
                    padding: '14px 0',
                    borderBottom: idx < rows.length - 1 ? '1px solid rgba(255, 255, 255, 0.06)' : 'none',
                    alignItems: 'flex-start',
                  }}
                >
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: 'var(--text-muted)',
                      letterSpacing: '0.05em',
                      textTransform: 'uppercase',
                      paddingTop: 2,
                    }}
                  >
                    {row.key}
                  </div>
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.875rem',
                      fontWeight: 500,
                      color: '#fcfdff',
                      wordBreak: 'break-all',
                      lineHeight: 1.6,
                    }}
                  >
                    {row.value || '—'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
