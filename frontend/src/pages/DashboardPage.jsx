import React, { useState, useEffect } from 'react';
import api from '../api/client';

const PROVIDER_COLORS = {
  google:       { bg: '#1a73e8', label: 'Google Genblaze' },
  nvidia:       { bg: '#76b900', label: 'NVIDIA NIM' },
  pollinations: { bg: '#6366f1', label: 'Pollinations.ai' },
  unknown:      { bg: '#6b7280', label: 'Unknown' },
};

function HealthDot({ health }) {
  const color = health === 'green' ? '#2ea44f' : health === 'yellow' ? '#e3a008' : '#d73a49';
  return (
    <span style={{
      display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
      background: color, marginRight: 6, boxShadow: `0 0 6px ${color}`,
    }} />
  );
}

function BarChart({ value, max, color }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ background: 'rgba(255,255,255,0.07)', borderRadius: 4, height: 8, overflow: 'hidden' }}>
      <div style={{
        width: `${pct}%`, height: '100%', background: color,
        borderRadius: 4, transition: 'width 0.6s ease',
      }} />
    </div>
  );
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchMetrics = async () => {
    try {
      const res = await api.get('/metrics');
      setMetrics(res.data);
      setLastRefresh(new Date().toLocaleTimeString());
      setError(null);
    } catch (err) {
      setError('Failed to load metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 15000); // auto-refresh every 15s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="page">
        <div className="loading-overlay">
          <div className="spinner" />
          <span>Loading pipeline metrics...</span>
        </div>
      </div>
    );
  }

  const providers = metrics?.providers || {};
  const maxTotal = Math.max(...Object.values(providers).map(p => p.total), 1);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">⚡ Pipeline Observability Dashboard</h1>
        <p className="page-subtitle">
          Live provider cascade health, generation metrics, and recent activity.
          {lastRefresh && <span className="text-muted"> · Last refreshed {lastRefresh}</span>}
        </p>
      </div>

      {error && (
        <div className="verify-result fail mb-6">
          <span className="verify-result-icon">❌</span>
          <div className="verify-result-content"><h3>{error}</h3></div>
        </div>
      )}

      {/* Summary Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16, marginBottom: 32 }}>
        {[
          { label: 'Total Generations', value: metrics?.total_generations ?? 0, icon: '🎨' },
          { label: 'Successful', value: metrics?.total_successful ?? 0, icon: '✅' },
          { label: 'Success Rate', value: `${metrics?.overall_success_rate_pct ?? 0}%`, icon: '📊' },
          { label: 'Providers Active', value: Object.keys(providers).length, icon: '🔀' },
        ].map(stat => (
          <div key={stat.label} className="card card-glass" style={{ textAlign: 'center', padding: '20px 12px' }}>
            <div style={{ fontSize: 28, marginBottom: 6 }}>{stat.icon}</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--color-accent)' }}>{stat.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-secondary)', marginTop: 4 }}>{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Provider Health Grid */}
      <div className="card card-glass mb-6" style={{ padding: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>
          🔀 Provider Cascade Health
        </h2>
        {Object.keys(providers).length === 0 ? (
          <p className="text-secondary text-sm">No generation events recorded yet. Generate an asset to see provider metrics.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {Object.entries(providers).map(([name, stats]) => {
              const info = PROVIDER_COLORS[name] || PROVIDER_COLORS.unknown;
              return (
                <div key={name}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <HealthDot health={stats.health} />
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{info.label}</span>
                      <span style={{
                        marginLeft: 8, background: info.bg, color: '#fff',
                        fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 8,
                        textTransform: 'uppercase',
                      }}>{name}</span>
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--color-secondary)' }}>
                      {stats.success}/{stats.total} · {stats.success_rate_pct}% · avg {stats.avg_latency_ms}ms
                    </div>
                  </div>
                  <BarChart value={stats.total} max={maxTotal} color={info.bg} />
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Recent Events */}
      <div className="card card-glass" style={{ padding: 24 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>
          📋 Recent Generation Events
        </h2>
        {(metrics?.recent_events || []).length === 0 ? (
          <p className="text-secondary text-sm">No events yet.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)', color: 'var(--color-secondary)' }}>
                  <th style={{ textAlign: 'left', padding: '6px 12px' }}>Status</th>
                  <th style={{ textAlign: 'left', padding: '6px 12px' }}>Provider</th>
                  <th style={{ textAlign: 'left', padding: '6px 12px' }}>Model</th>
                  <th style={{ textAlign: 'left', padding: '6px 12px' }}>Modality</th>
                  <th style={{ textAlign: 'right', padding: '6px 12px' }}>Latency</th>
                  <th style={{ textAlign: 'left', padding: '6px 12px' }}>Time</th>
                </tr>
              </thead>
              <tbody>
                {(metrics?.recent_events || []).map((ev, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '8px 12px' }}>
                      {ev.success ? '✅' : '❌'}
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      <span style={{
                        background: PROVIDER_COLORS[ev.provider]?.bg || '#6b7280',
                        color: '#fff', fontSize: 10, fontWeight: 700,
                        padding: '2px 6px', borderRadius: 8, textTransform: 'uppercase',
                      }}>{ev.provider}</span>
                    </td>
                    <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontSize: 11, color: 'var(--color-secondary)' }}>
                      {ev.model?.split('/').pop() || ev.model}
                    </td>
                    <td style={{ padding: '8px 12px' }}>{ev.modality}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600 }}>
                      {ev.latency_ms > 0 ? `${(ev.latency_ms / 1000).toFixed(1)}s` : '—'}
                    </td>
                    <td style={{ padding: '8px 12px', color: 'var(--color-secondary)', fontSize: 11 }}>
                      {ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <button className="btn btn-ghost btn-sm" onClick={fetchMetrics}>
            🔄 Refresh Now
          </button>
        </div>
      </div>
    </div>
  );
}
