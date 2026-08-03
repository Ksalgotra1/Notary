import React, { useState, useEffect } from 'react';
import {
  Activity,
  Sparkles,
  CheckCircle2,
  TrendingUp,
  Layers,
  RotateCw,
  XCircle,
  Clock,
} from 'lucide-react';
import api from '../api/client';

const PROVIDER_COLORS = {
  google:              { bg: '#1a73e8', label: 'Google GenAI' },
  'google-genai':      { bg: '#1a73e8', label: 'Google GenAI' },
  openai:              { bg: '#10a37f', label: 'OpenAI' },
  anthropic:           { bg: '#d97706', label: 'Anthropic' },
  nvidia:              { bg: '#76b900', label: 'NVIDIA NIM' },
  'nvidia-image':      { bg: '#76b900', label: 'NVIDIA NIM' },
  'huggingface-space': { bg: '#ffb000', label: 'Hugging Face Space' },
  huggingface:         { bg: '#ffb000', label: 'Hugging Face' },
  pollinations:        { bg: '#8b5cf6', label: 'Pollinations AI' },
};

export default function DashboardPage() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchMetrics = async () => {
    setRefreshing(true);
    try {
      const res = await api.get('/metrics');
      setMetrics(res.data);
      setLastRefresh(new Date().toLocaleTimeString());
      setError(null);
    } catch {
      setError('Failed to load metrics. Ensure backend server is running.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="page">
        <div className="loading-overlay">
          <div className="spinner" />
          <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
            Loading pipeline observability metrics...
          </span>
        </div>
      </div>
    );
  }

  const providers = metrics?.providers || {};

  const stats = [
    {
      label: 'Total Generations',
      value: metrics?.total_generations ?? 0,
      icon: Sparkles,
      color: '#ff801f',
    },
    {
      label: 'Successful',
      value: metrics?.total_successful ?? 0,
      icon: CheckCircle2,
      color: '#11ff99',
    },
    {
      label: 'Success Rate',
      value: `${metrics?.overall_success_rate_pct ?? 0}%`,
      icon: TrendingUp,
      color: '#3b9eff',
    },
    {
      label: 'Providers Active',
      value: Object.keys(providers).length,
      icon: Layers,
      color: '#ffc53d',
    },
  ];

  return (
    <div className="page">
      {/* Page Header */}
      <div className="page-header flex justify-between items-center" style={{ marginBottom: 28 }}>
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Activity style={{ width: 32, height: 32, color: '#3b9eff' }} />
            <span>Pipeline Observability</span>
          </h1>
          <p className="page-subtitle">
            Live provider cascade health, generation metrics, and execution lineage.
          </p>
        </div>

        {lastRefresh && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 14px',
              borderRadius: '9999px',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-strong)',
              fontSize: '0.8125rem',
              color: 'var(--text-secondary)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            <Clock style={{ width: 14, height: 14, color: 'var(--text-muted)' }} />
            <span>Refreshed {lastRefresh}</span>
          </div>
        )}
      </div>

      {error && (
        <div className="verify-result fail mb-6">
          <XCircle className="verify-result-icon text-danger" style={{ width: 24, height: 24 }} />
          <div className="verify-result-content">
            <h3>{error}</h3>
          </div>
        </div>
      )}

      {/* Top Stat Cards (4 in a row matching design) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 16,
          marginBottom: 24,
        }}
      >
        {stats.map((st) => {
          const IconComp = st.icon;
          return (
            <div
              key={st.label}
              className="card"
              style={{
                padding: '20px 24px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  color: 'var(--text-secondary)',
                  fontSize: '0.875rem',
                  fontFamily: 'var(--font-body)',
                }}
              >
                <IconComp style={{ width: 18, height: 18, color: st.color }} />
                <span>{st.label}</span>
              </div>
              <div
                style={{
                  fontSize: '2.5rem',
                  fontWeight: 600,
                  letterSpacing: '-0.02em',
                  color: 'var(--text-primary)',
                  fontFamily: 'var(--font-heading)',
                  marginTop: 12,
                  lineHeight: 1.1,
                }}
              >
                {st.value}
              </div>
            </div>
          );
        })}
      </div>

      {/* Main Grid: Left = Provider Cascade Health Table, Right = Recent Events Well */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: 20,
          alignItems: 'start',
        }}
      >
        {/* Left Column: Provider Cascade Health Table */}
        <div className="card" style={{ padding: 24 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 20,
              paddingBottom: 14,
              borderBottom: '1px solid var(--border)',
            }}
          >
            <h2 className="text-section" style={{ fontSize: '1.25rem', fontWeight: 600 }}>
              Provider Cascade Health
            </h2>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
              <thead>
                <tr
                  style={{
                    borderBottom: '1px solid var(--border-strong)',
                    color: 'var(--text-muted)',
                    textAlign: 'left',
                    fontFamily: 'var(--font-body)',
                  }}
                >
                  <th style={{ padding: '10px 10px', fontWeight: 500 }}>Provider</th>
                  <th style={{ padding: '10px 10px', fontWeight: 500 }}>Status</th>
                  <th style={{ padding: '10px 10px', fontWeight: 500 }}>Health</th>
                  <th style={{ padding: '10px 10px', fontWeight: 500 }}>Latency</th>
                  <th style={{ padding: '10px 10px', fontWeight: 500, textAlign: 'right' }}>Metrics</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(providers).length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ padding: '24px 10px', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                      No provider telemetry recorded yet.
                    </td>
                  </tr>
                ) : (
                  Object.entries(providers).map(([name, p]) => {
                    const formattedName = name === 'unknown'
                      ? 'Cascade Fallback (Failed)'
                      : name
                      ? name.split(/[-_]/).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
                      : 'Cascade Fallback (Failed)';
                    const providerLabel = PROVIDER_COLORS[name]?.label || formattedName;
                    const rawHealth = (p.health || (p.success_rate_pct >= 90 ? 'green' : p.success_rate_pct >= 60 ? 'yellow' : 'red')).toLowerCase();
                    const healthLabel = rawHealth === 'green' ? 'Green' : rawHealth === 'yellow' ? 'Yellow' : 'Red';
                    const statusColor = rawHealth === 'green' ? '#11ff99' : rawHealth === 'yellow' ? '#ffc53d' : '#ff2047';
                    const statusBg = rawHealth === 'green' ? 'rgba(17, 255, 153, 0.12)' : rawHealth === 'yellow' ? 'rgba(255, 197, 61, 0.12)' : 'rgba(255, 32, 71, 0.12)';
                    const statusBorder = rawHealth === 'green' ? 'rgba(17, 255, 153, 0.25)' : rawHealth === 'yellow' ? 'rgba(255, 197, 61, 0.25)' : 'rgba(255, 32, 71, 0.25)';

                    return (
                      <tr key={name} style={{ borderBottom: '1px solid var(--divider-soft)' }}>
                        <td style={{ padding: '14px 10px', fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>
                          {providerLabel}
                        </td>
                        <td style={{ padding: '14px 10px' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '3px 10px',
                              borderRadius: '6px',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              background: statusBg,
                              color: statusColor,
                              border: `1px solid ${statusBorder}`,
                              fontFamily: 'var(--font-body)',
                            }}
                          >
                            {healthLabel}
                          </span>
                        </td>
                        <td style={{ padding: '14px 10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ fontWeight: 600, fontSize: '0.8125rem', minWidth: 34, fontFamily: 'var(--font-body)' }}>
                              {p.success_rate_pct}%
                            </span>
                            <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 999, overflow: 'hidden', minWidth: 60 }}>
                              <div style={{ width: `${p.success_rate_pct}%`, height: '100%', background: statusColor, borderRadius: 999 }} />
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: '14px 10px', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                          {p.avg_latency_ms}ms
                        </td>
                        <td style={{ padding: '14px 10px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                          {p.success}/{p.total} {p.success_rate_pct}%
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Recent Generation Events Well */}
        <div className="card" style={{ padding: 24 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 20,
              paddingBottom: 14,
              borderBottom: '1px solid var(--border)',
            }}
          >
            <h2 className="text-section" style={{ fontSize: '1.25rem', fontWeight: 600 }}>
              Recent Generation Events
            </h2>
            <button
              className="btn btn-ghost btn-sm"
              onClick={fetchMetrics}
              disabled={refreshing}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: 'var(--font-body)' }}
            >
              <RotateCw
                style={{
                  width: 14,
                  height: 14,
                  animation: refreshing ? 'spin 0.7s linear infinite' : 'none',
                }}
              />
              <span>Refresh</span>
            </button>
          </div>

          <div
            style={{
              background: 'var(--bg-deep)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius)',
              padding: '24px',
              minHeight: '340px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: (metrics?.recent_events || []).length === 0 ? 'center' : 'flex-start',
              alignItems: (metrics?.recent_events || []).length === 0 ? 'center' : 'stretch',
            }}
          >
            {(metrics?.recent_events || []).length === 0 ? (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                <Clock style={{ width: 40, height: 40, opacity: 0.35, marginBottom: 12, margin: '0 auto' }} />
                <p style={{ fontSize: '0.875rem', fontFamily: 'var(--font-body)' }}>No recent generation events logged.</p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                  <thead>
                    <tr
                      style={{
                        borderBottom: '1px solid var(--border-strong)',
                        color: 'var(--text-muted)',
                        fontFamily: 'var(--font-body)',
                      }}
                    >
                      <th style={{ textAlign: 'left', padding: '8px' }}>Status</th>
                      <th style={{ textAlign: 'left', padding: '8px' }}>Provider</th>
                      <th style={{ textAlign: 'left', padding: '8px' }}>Model</th>
                      <th style={{ textAlign: 'right', padding: '8px' }}>Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(metrics?.recent_events || []).map((ev, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--divider-soft)' }}>
                        <td style={{ padding: '10px 8px' }}>
                          {ev.success ? (
                            <CheckCircle2 style={{ width: 16, height: 16, color: '#11ff99' }} />
                          ) : (
                            <XCircle style={{ width: 16, height: 16, color: '#ff2047' }} />
                          )}
                        </td>
                        <td style={{ padding: '10px 8px', fontWeight: 500, fontFamily: 'var(--font-body)' }}>
                          {ev.provider}
                        </td>
                        <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {ev.model?.split('/').pop() || ev.model}
                        </td>
                        <td style={{ padding: '10px 8px', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                          {ev.latency_ms > 0 ? `${ev.latency_ms}ms` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
