import React, { useState } from 'react';
import StatusBadge from './StatusBadge';

export default function ComplianceCard({ regulation }) {
  const [expanded, setExpanded] = useState(false);

  if (!regulation) return null;

  return (
    <div className="compliance-card">
      <div
        className="compliance-card-header"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="compliance-card-title">
          <span className="compliance-card-regulation">
            {regulation.regulation_name}
          </span>
          <span className="compliance-card-date">
            (Effective: {regulation.effective_date})
          </span>
        </div>
        <div className="compliance-card-score">
          <span>
            {regulation.passed}/{regulation.total} checks passed
          </span>
          <StatusBadge
            status={regulation.compliant ? 'pass' : 'fail'}
            type="compliance"
          />
          <span className={`manifest-toggle ${expanded ? 'open' : ''}`}>
            ▼
          </span>
        </div>
      </div>

      {expanded && (
        <>
          <div className="compliance-checks">
            {regulation.checks.map((check) => (
              <div key={check.requirement_id} className="compliance-check">
                <div className={`compliance-check-icon ${check.status}`}>
                  {check.status === 'pass' && '✓'}
                  {check.status === 'fail' && '✗'}
                  {check.status === 'partial' && '~'}
                  {check.status === 'not_applicable' && '—'}
                </div>
                <div className="compliance-check-content">
                  <div className="compliance-check-id">
                    {check.requirement_id}
                  </div>
                  <div className="compliance-check-desc">
                    {check.description}
                  </div>
                  <div className="compliance-check-detail">{check.detail}</div>
                </div>
                <StatusBadge status={check.status} type="compliance" />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
