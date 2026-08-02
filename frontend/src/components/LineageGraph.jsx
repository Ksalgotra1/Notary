import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';

/**
 * Interactive SVG-based Provenance Lineage DAG.
 * Renders nodes (assets) and edges (parent→child) with:
 * - Color-coded provider badges
 * - Clickable nodes that navigate to asset details
 * - Highlight for the currently-viewed asset
 */

const PROVIDER_STYLES = {
  google:       { fill: '#1a73e8', label: 'Google' },
  nvidia:       { fill: '#76b900', label: 'NVIDIA' },
  pollinations: { fill: '#6366f1', label: 'Pollinations' },
  unknown:      { fill: '#6b7280', label: 'Unknown' },
};

const NODE_W = 240;
const NODE_H = 80;
const H_GAP = 60;
const V_GAP = 32;

function layoutTree(nodes, edges, root) {
  const children = {};
  for (const e of edges) {
    if (!children[e.source]) children[e.source] = [];
    children[e.source].push(e.target);
  }

  const positions = {};
  let nextX = 0;

  function layout(id, depth) {
    const kids = children[id] || [];
    if (kids.length === 0) {
      positions[id] = { x: nextX, y: depth * (NODE_H + V_GAP) };
      nextX += NODE_W + H_GAP;
    } else {
      for (const kid of kids) {
        layout(kid, depth + 1);
      }
      const firstChild = positions[kids[0]];
      const lastChild = positions[kids[kids.length - 1]];
      positions[id] = {
        x: (firstChild.x + lastChild.x) / 2,
        y: depth * (NODE_H + V_GAP),
      };
    }
  }

  if (root && nodes.find(n => n.run_id === root)) {
    layout(root, 0);
  }
  // Handle orphan nodes (not reachable from root)
  for (const n of nodes) {
    if (!positions[n.run_id]) {
      positions[n.run_id] = { x: nextX, y: 0 };
      nextX += NODE_W + H_GAP;
    }
  }

  return positions;
}

export default function LineageGraph({ runId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const svgRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/assets/${runId}/lineage`);
        setData(res.data);
      } catch (e) {
        setError('Failed to load lineage data.');
      } finally {
        setLoading(false);
      }
    })();
  }, [runId]);

  if (loading) return <div className="loading-overlay"><div className="spinner" /><span>Loading lineage...</span></div>;
  if (error) return <div className="text-secondary text-sm">{error}</div>;
  if (!data || data.total_nodes <= 1) {
    return (
      <div className="card card-glass" style={{ padding: 20, textAlign: 'center' }}>
        <p className="text-secondary text-sm">
          This asset has no remix lineage. Use <b>🔄 Remix Asset</b> to create a derivation chain.
        </p>
      </div>
    );
  }

  const positions = layoutTree(data.nodes, data.edges, data.root);
  const allX = Object.values(positions).map(p => p.x);
  const allY = Object.values(positions).map(p => p.y);
  const svgW = Math.max(...allX) + NODE_W + 40;
  const svgH = Math.max(...allY) + NODE_H + 40;

  return (
    <div className="card card-glass" style={{ padding: 20, overflowX: 'auto' }}>
      <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>
        🕸️ Provenance Lineage Graph ({data.total_nodes} nodes)
      </h3>
      <svg
        ref={svgRef}
        width={svgW}
        height={svgH}
        viewBox={`-20 -20 ${svgW} ${svgH}`}
        style={{ minWidth: 300 }}
      >
        <defs>
          <marker id="arrowhead" viewBox="0 0 10 8" refX="10" refY="4"
                  markerWidth="8" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 4 L 0 8 z" fill="#6366f1" />
          </marker>
        </defs>

        {/* Edges */}
        {data.edges.map((e, i) => {
          const from = positions[e.source];
          const to = positions[e.target];
          if (!from || !to) return null;
          return (
            <line
              key={i}
              x1={from.x + NODE_W / 2}
              y1={from.y + NODE_H}
              x2={to.x + NODE_W / 2}
              y2={to.y}
              stroke="#6366f1"
              strokeWidth={2}
              strokeDasharray={e.source === data.root ? "none" : "4 4"}
              markerEnd="url(#arrowhead)"
              opacity={0.6}
            />
          );
        })}

        {/* Nodes */}
        {data.nodes.map(node => {
          const pos = positions[node.run_id];
          if (!pos) return null;
          const isCurrent = node.run_id === runId;
          const prov = PROVIDER_STYLES[node.provider] || PROVIDER_STYLES.unknown;
          const isRoot = node.run_id === data.root;
          const statusColor = node.verify_status === 'pass' ? '#2ea44f'
            : node.verify_status === 'fail' ? '#d73a49' : '#e3a008';

          return (
            <g
              key={node.run_id}
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/assets/${node.run_id}`)}
            >
              <rect
                x={pos.x} y={pos.y}
                width={NODE_W} height={NODE_H}
                rx={10}
                fill={isCurrent ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)'}
                stroke={isCurrent ? '#6366f1' : 'rgba(255,255,255,0.1)'}
                strokeWidth={isCurrent ? 2.5 : 1}
              />
              {/* Status dot */}
              <circle cx={pos.x + NODE_W - 12} cy={pos.y + 12} r={5} fill={statusColor} />

              {/* Provider pill */}
              <rect x={pos.x + 8} y={pos.y + 8} width={70} height={16} rx={8} fill={prov.fill} />
              <text x={pos.x + 43} y={pos.y + 20} textAnchor="middle"
                    fill="#fff" fontSize={9} fontWeight={700}>{prov.label}</text>

              {/* Root badge */}
              {isRoot && (
                <>
                  <rect x={pos.x + 82} y={pos.y + 8} width={40} height={16} rx={8} fill="#e3a008" />
                  <text x={pos.x + 102} y={pos.y + 20} textAnchor="middle"
                        fill="#fff" fontSize={8} fontWeight={700}>ROOT</text>
                </>
              )}

              {/* Prompt snippet */}
              <text x={pos.x + 10} y={pos.y + 42} fill="#ddd" fontSize={11} fontWeight={600}>
                {(node.prompt || '').slice(0, 28)}{(node.prompt || '').length > 28 ? '…' : ''}
              </text>

              {/* Run ID + date */}
              <text x={pos.x + 10} y={pos.y + 60} fill="#888" fontSize={9} fontFamily="monospace">
                {node.run_id.slice(0, 8)}… · {(node.created_at || '').slice(0, 10)}
              </text>

              {/* Current indicator */}
              {isCurrent && (
                <text x={pos.x + NODE_W - 14} y={pos.y + NODE_H - 8}
                      fill="#6366f1" fontSize={9} fontWeight={700} textAnchor="end">YOU</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
