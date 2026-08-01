import React from 'react';

export default function StatusBadge({ status, type = 'status' }) {
  if (type === 'modality') {
    return (
      <span className={`badge badge-${status}`}>
        {status === 'video' ? '🎥 Video' : '🖼️ Image'}
      </span>
    );
  }

  if (type === 'compliance') {
    const classMap = {
      pass: 'badge-pass',
      fail: 'badge-fail',
      partial: 'badge-partial',
      not_applicable: 'badge-na',
    };
    const labelMap = {
      pass: '✓ PASS',
      fail: '✗ FAIL',
      partial: '~ PARTIAL',
      not_applicable: 'N/A',
    };
    return (
      <span className={`badge ${classMap[status] || 'badge-unverified'}`}>
        {labelMap[status] || status}
      </span>
    );
  }

  // Verification status
  if (status === true || status === 'verified' || status === 'pass') {
    return <span className="badge badge-verified">✓ Verified</span>;
  }
  if (status === false || status === 'failed' || status === 'fail') {
    return <span className="badge badge-failed">⚠ Tampered / Failed</span>;
  }
  return <span className="badge badge-unverified">Unverified</span>;
}
