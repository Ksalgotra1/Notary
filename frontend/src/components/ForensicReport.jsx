import React from 'react';
import { Microscope } from 'lucide-react';

export default function ForensicReport({ forensic }) {
  if (!forensic) return null;

  return (
    <div className="forensic-report">
      <div className="forensic-header">
        <Microscope style={{ width: 20, height: 20, color: '#ff2047' }} />
        <h3 className="forensic-title">
          AI Forensic Analysis — Tamper Evidence Detected
        </h3>
        <span
          className={`badge forensic-severity forensic-severity-${forensic.severity}`}
        >
          {forensic.severity} severity
        </span>
      </div>

      <div className="forensic-modifications">
        <h4>Modifications Detected</h4>
        <ul>
          {forensic.modifications_detected.map((mod, idx) => (
            <li key={idx}>{mod}</li>
          ))}
        </ul>
      </div>

      <div className="forensic-conclusion">
        "{forensic.conclusion}"
      </div>

      <div className="forensic-model">
        Analyzed by {forensic.analysis_model} Vision Pipeline
      </div>
    </div>
  );
}
