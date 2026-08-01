import React, { useState } from 'react';

export default function ManifestPanel({ asset }) {
  const [isOpen, setIsOpen] = useState(false);
  const [viewJson, setViewJson] = useState(false);

  if (!asset) return null;

  return (
    <div className="manifest-panel">
      <div className="manifest-header" onClick={() => setIsOpen(!isOpen)}>
        <h3>📜 Provenance Manifest</h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-secondary font-mono">
            {asset.run_id ? asset.run_id.slice(0, 8) + '...' : ''}
          </span>
          <span className={`manifest-toggle ${isOpen ? 'open' : ''}`}>▼</span>
        </div>
      </div>

      {isOpen && (
        <div className="manifest-body">
          <div className="flex justify-between items-center mb-4">
            <span className="input-label">Manifest Breakdown</span>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setViewJson(!viewJson)}
            >
              {viewJson ? 'View Structured' : 'View Raw JSON'}
            </button>
          </div>

          {viewJson ? (
            <pre className="manifest-json">
              {JSON.stringify(asset, null, 2)}
            </pre>
          ) : (
            <div className="manifest-rows">
              <div className="manifest-row">
                <div className="manifest-key">Run ID</div>
                <div className="manifest-value">{asset.run_id}</div>
              </div>
              {asset.parent_run_id && (
                <div className="manifest-row">
                  <div className="manifest-key">Parent Run ID</div>
                  <div className="manifest-value">{asset.parent_run_id}</div>
                </div>
              )}
              <div className="manifest-row">
                <div className="manifest-key">Provider</div>
                <div className="manifest-value">{asset.provider}</div>
              </div>
              <div className="manifest-row">
                <div className="manifest-key">Model</div>
                <div className="manifest-value">{asset.model}</div>
              </div>
              <div className="manifest-row">
                <div className="manifest-key">Modality</div>
                <div className="manifest-value">{asset.modality}</div>
              </div>
              <div className="manifest-row">
                <div className="manifest-key">Prompt</div>
                <div className="manifest-value">{asset.prompt}</div>
              </div>
              <div className="manifest-row">
                <div className="manifest-key">SHA-256 Hash</div>
                <div className="manifest-value">{asset.sha256}</div>
              </div>
              <div className="manifest-row">
                <div className="manifest-key">Created At</div>
                <div className="manifest-value">{asset.created_at}</div>
              </div>
              <div className="manifest-row">
                <div className="manifest-key">B2 Asset URL</div>
                <div className="manifest-value">{asset.b2_asset_url}</div>
              </div>
              <div className="manifest-row">
                <div className="manifest-key">B2 Manifest URI</div>
                <div className="manifest-value">{asset.b2_manifest_url}</div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
