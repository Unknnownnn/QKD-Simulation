/*
  NetworkView.jsx — Interactive quantum network topology visualization,
  live QBER monitoring, and smart routing toggle.
*/
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { FiRefreshCw, FiActivity, FiGitBranch, FiAlertTriangle } from 'react-icons/fi';
import { getTopology, setSmartRouting as apiSetSmartRouting, getNetworkAlerts } from '../api';

const NODE_RADIUS = 24;
const COLORS = {
  alice: '#74b9ff', bob: '#00b894', relay: '#a29bfe', eve: '#d63031',
  safe: '#00b894', warning: '#fdcb6e', critical: '#d63031',
  routeActive: '#74b9ff', routeDim: 'rgba(80,100,220,0.2)',
};

function getNodeColor(node) {
  if (node.compromised) return COLORS.critical;
  return COLORS[node.role] || COLORS.relay;
}

function getLinkColor(link) {
  if (link.compromised) return COLORS.critical;
  if (link.status === 'warning') return COLORS.warning;
  return COLORS.safe;
}

function TopologyCanvas({ topology }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !topology) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;

    ctx.clearRect(0, 0, W, H);

    const nodes = topology.nodes || [];
    const links = topology.links || [];
    const route = topology.active_route || [];

    // Map node positions
    const nodeMap = {};
    nodes.forEach(n => {
      nodeMap[n.id] = { ...n, px: n.x * (W - 80) + 40, py: n.y * (H - 80) + 40 };
    });

    // Draw links
    links.forEach(link => {
      const src = nodeMap[link.src];
      const dst = nodeMap[link.dst];
      if (!src || !dst) return;

      // Check if on active route
      const onRoute = route.length > 1 && route.some((r, i) =>
        i < route.length - 1 && (
          (route[i] === link.src && route[i + 1] === link.dst) ||
          (route[i] === link.dst && route[i + 1] === link.src)
        )
      );

      ctx.beginPath();
      ctx.moveTo(src.px, src.py);
      ctx.lineTo(dst.px, dst.py);
      ctx.strokeStyle = link.compromised ? COLORS.critical :
                        onRoute ? COLORS.routeActive : COLORS.routeDim;
      ctx.lineWidth = onRoute ? 3 : 1.5;
      if (link.compromised) {
        ctx.setLineDash([5, 5]);
      } else {
        ctx.setLineDash([]);
      }
      ctx.stroke();
      ctx.setLineDash([]);

      // QBER label on link
      const mx = (src.px + dst.px) / 2;
      const my = (src.py + dst.py) / 2;
      ctx.font = '9px Inter';
      ctx.fillStyle = link.qber > 0.11 ? COLORS.critical : '#7986cb';
      ctx.textAlign = 'center';
      ctx.fillText(`${(link.qber * 100).toFixed(1)}%`, mx, my - 6);

      if (link.attack_type !== 'none') {
        ctx.fillStyle = COLORS.critical;
        ctx.font = 'bold 9px Inter';
        ctx.fillText(`⚡${link.attack_type}`, mx, my + 8);
      }
    });

    // Draw nodes
    nodes.forEach(node => {
      const n = nodeMap[node.id];
      if (!n) return;

      // Glow for compromised
      if (node.compromised) {
        ctx.beginPath();
        ctx.arc(n.px, n.py, NODE_RADIUS + 6, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(214, 48, 49, 0.15)';
        ctx.fill();
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(n.px, n.py, NODE_RADIUS, 0, Math.PI * 2);
      const color = getNodeColor(node);
      ctx.fillStyle = color + '22';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Node icon
      ctx.font = '16px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const icon = node.role === 'alice' ? '🧑' :
                   node.role === 'bob' ? '👤' :
                   node.role === 'eve' ? '🕵️' : '🔄';
      ctx.fillText(icon, n.px, n.py);

      // Label
      ctx.font = '11px Inter';
      ctx.fillStyle = '#e8eaf6';
      ctx.fillText(node.label, n.px, n.py + NODE_RADIUS + 14);

      // Status
      ctx.font = '9px Inter';
      ctx.fillStyle = node.compromised ? COLORS.critical : '#7986cb';
      ctx.fillText(node.compromised ? '⚠ Compromised' : node.id, n.px, n.py + NODE_RADIUS + 26);
    });

  }, [topology]);

  return (
    <canvas ref={canvasRef} width={700} height={400}
      style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid rgba(80,100,220,0.15)' }}
    />
  );
}

export default function NetworkView({ topology, onRefresh }) {
  const [alerts, setAlerts] = useState([]);
  const [smartRouting, setSmartRouting] = useState(topology?.smart_routing_enabled ?? true);

  useEffect(() => {
    getNetworkAlerts().then(setAlerts).catch(() => {});
  }, [topology]);

  const toggleSmartRouting = async () => {
    const newVal = !smartRouting;
    setSmartRouting(newVal);
    await apiSetSmartRouting(newVal);
    onRefresh?.();
  };

  const route = topology?.active_route || [];

  return (
    <div style={styles.container}>
      {/* Main canvas */}
      <div style={styles.mainPanel}>
        <div style={styles.panelHeader}>
          <h3 style={styles.title}><FiGitBranch size={16} /> Network Topology</h3>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn btn-sm" onClick={onRefresh}><FiRefreshCw size={12} /></button>
          </div>
        </div>
        <TopologyCanvas topology={topology} />

        {/* Route display */}
        <div style={styles.routeBar}>
          <span style={{ fontSize: '12px', color: '#7986cb' }}>Active Route:</span>
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            {route.map((node, i) => (
              <React.Fragment key={node}>
                <span className="badge badge-info">{node}</span>
                {i < route.length - 1 && <span style={{ color: '#74b9ff' }}>→</span>}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Link status grid */}
        <div style={styles.linkGrid}>
          {(topology?.links || []).filter(l => l.src < l.dst).map(link => (
            <div key={`${link.src}→${link.dst}`} style={{
              ...styles.linkCard,
              borderColor: link.compromised ? COLORS.critical :
                          link.status === 'warning' ? COLORS.warning : 'rgba(80,100,220,0.2)',
            }}>
              <div style={{ fontSize: '12px', fontWeight: 600 }}>
                {link.src} ↔ {link.dst}
              </div>
              <div style={{
                fontSize: '14px', fontWeight: 700,
                color: link.qber > 0.2 ? COLORS.critical :
                       link.qber > 0.11 ? COLORS.warning : COLORS.safe,
              }}>
                {(link.qber * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: '10px', color: '#7986cb' }}>QBER</div>
              {link.attack_type !== 'none' && (
                <span className="badge badge-critical" style={{ marginTop: '4px' }}>
                  ⚡ {link.attack_type}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Side panel */}
      <div style={styles.sidePanel}>
        {/* Smart Routing Toggle */}
        <div className="card" style={{ marginBottom: '12px' }}>
          <h4 style={styles.subTitle}><FiActivity size={14} /> Smart Routing</h4>
          <div style={styles.toggleRow}>
            <span style={{ fontSize: '12px', color: smartRouting ? '#00b894' : '#d63031' }}>
              {smartRouting ? '✓ Enabled' : '✗ Disabled'}
            </span>
            <button
              className={`btn btn-sm ${smartRouting ? 'btn-green' : 'btn-red'}`}
              onClick={async () => {
                const newVal = !smartRouting;
                setSmartRouting(newVal);
                try {
                  await apiSetSmartRouting(newVal);
                } catch (err) {
                  // setSmartRouting is also the imported API function name; 
                  // handle the conflict by renaming inline
                }
                onRefresh?.();
              }}
            >
              {smartRouting ? 'Disable' : 'Enable'}
            </button>
          </div>
          <p style={{ fontSize: '11px', color: '#7986cb', marginTop: '8px' }}>
            {smartRouting
              ? 'SDN controller automatically reroutes around compromised links.'
              : 'Traffic flows through shortest path regardless of security status.'}
          </p>
        </div>

        {/* Alerts */}
        <div className="card">
          <h4 style={styles.subTitle}><FiAlertTriangle size={14} /> Network Alerts</h4>
          <div style={styles.alertList}>
            {alerts.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px', color: '#7986cb', fontSize: '12px' }}>
                No alerts
              </div>
            ) : (
              alerts.slice(0, 10).map((a, i) => (
                <div key={i} style={styles.alertItem}>
                  <span style={{ color: a.threshold === 'critical' ? '#d63031' : '#fdcb6e' }}>
                    {a.threshold === 'critical' ? '🔴' : '🟡'}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '11px' }}>
                      {a.link_id} — QBER {(a.qber * 100).toFixed(1)}%
                    </div>
                    <div style={{ fontSize: '10px', color: '#7986cb' }}>
                      {a.action_taken}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: { display: 'flex', flex: 1, overflow: 'hidden' },
  mainPanel: { flex: 1, padding: '16px', overflow: 'auto' },
  sidePanel: {
    width: '280px', padding: '16px', overflow: 'auto',
    borderLeft: '1px solid rgba(80,100,220,0.2)', background: 'rgba(14,14,42,0.3)',
  },
  panelHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px',
  },
  title: {
    fontSize: '15px', fontWeight: 600, color: '#e8eaf6',
    display: 'flex', alignItems: 'center', gap: '8px',
  },
  subTitle: {
    fontSize: '13px', fontWeight: 600, color: '#e8eaf6',
    display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px',
  },
  routeBar: {
    display: 'flex', alignItems: 'center', gap: '12px',
    padding: '10px 14px', marginTop: '12px',
    background: 'rgba(0,0,0,0.2)', borderRadius: '8px',
  },
  linkGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
    gap: '8px', marginTop: '12px',
  },
  linkCard: {
    padding: '10px', textAlign: 'center',
    background: 'rgba(17,17,48,0.8)', border: '1px solid rgba(80,100,220,0.2)',
    borderRadius: '8px',
  },
  toggleRow: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  },
  alertList: { maxHeight: '400px', overflow: 'auto' },
  alertItem: {
    display: 'flex', alignItems: 'flex-start', gap: '8px',
    padding: '8px 0', borderBottom: '1px solid rgba(80,100,220,0.1)',
  },
};
