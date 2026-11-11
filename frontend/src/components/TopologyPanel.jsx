import { useState } from "react";
import { getAssetDetail, getIncidentAnalysis } from "../services/api";
import IncidentModal from "./IncidentModal.jsx";
import { timeAgo } from "../hooks";

const STATUS_COLORS = {
  monitored: "#22d3ee",
  attention: "#eab308",
  high_risk: "#f97316",
  critical: "#ef4444",
  inactive: "#64748b",
};

/**
 * Simple circular layout graph built from REAL topology data:
 * nodes = observed assets, edges = observed src->dst pairs.
 * Animated flow is shown only on edges with events in the
 * last 10 minutes (real recent activity, never decorative).
 */
export default function TopologyPanel({ topology }) {
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [openIncident, setOpenIncident] = useState(null);

  const nodes = topology?.nodes || [];
  const edges = topology?.edges || [];
  const recent = topology?.recent_events || [];

  const positioned = nodes.map((node, i) => {
    const n = Math.max(nodes.length, 1);
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
    const r = n === 1 ? 0 : 0.72;
    return {
      ...node,
      x: 50 + (r / 2) * 92 * Math.cos(angle),
      y: 50 + (r / 2) * 86 * Math.sin(angle),
    };
  });

  const byIp = Object.fromEntries(positioned.map((n) => [n.ip, n]));

  const now = Date.now();
  const recentByIp = {};
  recent.forEach((ev) => {
    const t = new Date(ev.created_at).getTime();
    if (now - t < 10 * 60 * 1000) {
      [ev.source_ip, ev.destination_ip].forEach((ip) => {
        if (ip && now - t < 10 * 60 * 1000) {
          recentByIp[ip] = true;
        }
      });
    }
  });

  const selectNode = async (ip) => {
    setSelected(ip);
    setDetail(null);
    try {
      const data = await getAssetDetail(ip);
      setDetail(data);
    } catch {
      setDetail({ error: true, ip });
    }
  };

  const openAnalysis = async (incident) => {
    try {
      const analysis = await getIncidentAnalysis(incident.id);
      setOpenIncident({ ...incident, analysis });
    } catch {
      setOpenIncident(incident);
    }
  };

  return (
    <div className="panel area-topo">
      <div className="panel-head">
        <h3>Live Network Topology</h3>
        <span className="meta">{nodes.length} ativos observados · {edges.length} ligações reais</span>
      </div>

      {nodes.length === 0 ? (
        <div className="state">
          Ainda não há ativos observados. Os nós aparecem quando o Suricata
          detetar tráfego ou registares ativos manualmente em Assets.
        </div>
      ) : (
        <svg className="topo-svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
          <defs>
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="1.2" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {edges.map((edge, i) => {
            const a = byIp[edge.source];
            const b = byIp[edge.target];
            if (!a || !b) return null;

            const last = new Date(edge.last_event_at).getTime();
            const flowing = now - last < 10 * 60 * 1000;

            return (
              <path
                key={i}
                className={`edge ${flowing ? "flow" : ""}`}
                d={`M ${a.x} ${a.y} Q ${(a.x + b.x) / 2 + (b.y - a.y) * 0.12} ${(a.y + b.y) / 2 - (b.x - a.x) * 0.12} ${b.x} ${b.y}`}
                stroke={flowing ? "#22d3ee" : "#31445c"}
                filter={flowing ? "url(#glow)" : undefined}
              >
                <title>{`${edge.source} → ${edge.target} · ${edge.incident_count} incidentes`}</title>
              </path>
            );
          })}

          {positioned.map((node) => {
            const color = STATUS_COLORS[node.status] || STATUS_COLORS.inactive;
            const hot = recentByIp[node.ip];
            return (
              <g
                key={node.ip}
                className="topo-node"
                onClick={() => selectNode(node.ip)}
                filter="url(#glow)"
              >
                {hot && (
                  <circle
                    className="pulse"
                    cx={node.x}
                    cy={node.y}
                    r={6}
                    fill="none"
                    stroke={color}
                    strokeWidth={0.5}
                  />
                )}
                <circle
                  className="core"
                  cx={node.x}
                  cy={node.y}
                  r={3.2}
                  stroke={color}
                  filter="url(#glow)"
                />
                <text x={node.x} y={node.y + 7}>
                  {(node.name || node.ip).slice(0, 18)}
                </text>
              </g>
            );
          })}
        </svg>
      )}

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2>{detail?.name || selected}</h2>
                <span className="muted">
                  {detail?.asset_type || "?"} · {selected} ·{" "}
                  {detail?.status || "…"}
                  {detail?.last_seen_at && ` · visto ${timeAgo(detail.last_seen_at)} atrás`}
                </span>
              </div>
              <button className="close-x" onClick={() => setSelected(null)}>✕</button>
            </div>

            {!detail && <div className="state">a carregar…</div>}

            {detail?.error && (
              <div className="state error">Não foi possível obter o detalhe do ativo.</div>
            )}

            {detail && !detail.error && (
              <>
                <div className="kv">
                  <div><span>IP</span><b>{detail.ip}</b></div>
                  <div><span>Tipo</span><b>{detail.asset_type}</b></div>
                  <div><span>Estado</span><b>{detail.status}</b></div>
                  <div><span>Incidentes abertos</span><b>{detail.open_incidents}</b></div>
                  <div><span>Primeira vez visto</span><b>{detail.first_seen_at?.slice(0, 16).replace("T", " ")}</b></div>
                  <div><span>Última vez visto</span><b>{detail.last_seen_at?.slice(0, 16).replace("T", " ")}</b></div>
                </div>

                <h4 className="muted" style={{ marginBottom: 6 }}>Incidentes recentes</h4>
                {detail.recent_incidents?.length === 0 && (
                  <div className="state">Sem incidentes associados.</div>
                )}
                {detail.recent_incidents?.map((inc) => (
                  <div className="list-item" key={inc.id} onClick={() => openAnalysis(inc)}>
                    <span className={`sev ${inc.severity}`}>{inc.severity}</span>
                    {inc.event_type}
                    <span className="when">{timeAgo(inc.created_at)}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}

      {openIncident && (
        <IncidentModal
          incident={openIncident}
          onClose={() => setOpenIncident(null)}
          onChanged={() => setOpenIncident(null)}
        />
      )}
    </div>
  );
}
