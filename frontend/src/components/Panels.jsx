import { timeAgo } from "../hooks";

export function CriticalIncidents({ incidents, loading, onSelect }) {
  const open = (incidents || []).filter((i) =>
    ["new", "investigating", "confirmed"].includes(i.status)
  );
  const top = open
    .sort((a, b) => {
      const rank = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFORMATIONAL: 4 };
      return rank[a.severity] - rank[b.severity];
    })
    .slice(0, 6);

  return (
    <div className="panel area-critical">
      <div className="panel-head">
        <h3>Critical Incidents</h3>
        <span className="meta">{open.length} abertos</span>
      </div>

      {loading && <div className="state">a carregar…</div>}

      {!loading && top.length === 0 && (
        <div className="state">Sem incidentes abertos de severidade elevada.</div>
      )}

      {top.map((incident) => (
        <div className="list-item" key={incident.id} onClick={() => onSelect(incident)}>
          <span className={`sev ${incident.severity}`}>{incident.severity}</span>
          <div>
            <div style={{ fontWeight: 600 }}>{incident.event_type}</div>
            <div style={{ fontSize: 10.5, color: "var(--text-faint)" }}>
              {incident.source_ip} → {incident.destination_ip || "—"} · {incident.status}
            </div>
          </div>
          <span className="when">{timeAgo(incident.created_at)}</span>
        </div>
      ))}
    </div>
  );
}

export function SecurityPosture({ posture }) {
  const statusColor = {
    healthy: "var(--green)",
    attention: "var(--yellow)",
    high_risk: "var(--orange)",
    critical: "var(--red)",
    insufficient_data: "var(--gray)",
  };

  const maxTrend = Math.max(
    1,
    ...(posture?.trend || []).map((t) => t.new_incidents)
  );

  return (
    <div className="panel area-posture">
      <div className="panel-head">
        <h3>Security Posture</h3>
      </div>

      {!posture && <div className="state">a carregar…</div>}

      {posture && posture.score === null && (
        <div className="state">{posture.message}</div>
      )}

      {posture && posture.score !== null && (
        <>
          <div className="score-line">
            <span className="score" style={{ color: statusColor[posture.status] }}>
              {posture.score}
            </span>
            <span className="of">/ 100 · {posture.status}</span>
          </div>

          <div className="trend-bars">
            {posture.trend.map((t) => (
              <div
                className="bar"
                key={t.date}
                style={{ height: `${(t.new_incidents / maxTrend) * 100}%` }}
                title={`${t.date}: ${t.new_incidents} deteções`}
              />
            ))}
          </div>
          <div className="trend-labels">
            {posture.trend.map((t) => (
              <span key={t.date}>{t.date.slice(5)}</span>
            ))}
          </div>

          <div className="chips">
            {Object.entries(posture.breakdown)
              .filter(([, n]) => n > 0)
              .map(([severity, n]) => (
                <span className="chip" key={severity}>
                  <b>{severity}</b> ×{n}
                </span>
              ))}
            {posture.breakdown && Object.values(posture.breakdown).every((n) => n === 0) && (
              <span className="chip">Sem incidentes abertos</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export function AlertOverview({ stats }) {
  if (!stats) {
    return (
      <div className="panel"><div className="panel-head"><h3>Alert Overview</h3></div><div className="state">a carregar…</div></div>
    );
  }

  const severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"];
  const max = Math.max(1, ...severities.map((s) => stats.by_severity[s] || 0));

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>Alert Overview</h3>
        <span className="meta">total: {stats.total}</span>
      </div>

      <div className="counts">
        {severities.map((severity) => (
          <div className={`count ${severity}`} key={severity}>
            <strong>{stats.by_severity[severity] || 0}</strong>
            <span>{severity.slice(0, 4).toLowerCase()}</span>
          </div>
        ))}
      </div>

      <div className="hist-bars">
        {severities.map((severity) => (
          <div
            className="bar"
            key={severity}
            style={{ height: `${((stats.by_severity[severity] || 0) / max) * 100}%` }}
            title={`${severity}: ${stats.by_severity[severity] || 0}`}
          />
        ))}
      </div>
      <div className="trend-labels">
        {severities.map((severity) => (
          <span key={severity}>{severity.slice(0, 4).toLowerCase()}</span>
        ))}
      </div>
    </div>
  );
}

export function ThreatIntelligence({ intel }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h3>Threat Intelligence</h3>
        <span className="meta">
          {intel ? `${intel.analyses_considered} análises analisadas` : ""}
        </span>
      </div>

      {!intel && <div className="state">a carregar…</div>}

      {intel && (
        <>
          <div className="chips">
            {Object.entries(intel.threat_levels).length === 0 && (
              <span className="chip">Sem análises IA ainda</span>
            )}
            {Object.entries(intel.threat_levels).map(([level, n]) => (
              <span className="chip" key={level}>
                <b>{level}</b> ×{n}
              </span>
            ))}
          </div>

          <div style={{ marginTop: 10 }}>
            {intel.indicators.slice(0, 6).map((ind, i) => (
              <div className="ioc" key={i}>
                <span className="t">{ind.type || "ioc"}</span>
                <span className="v">{ind.value || String(ind)}</span>
                <span className="when">#{ind.incident_id}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function AssetHealth({ assets }) {
  if (!assets) {
    return (
      <div className="panel"><div className="panel-head"><h3>Asset Health</h3></div><div className="state">a carregar…</div></div>
    );
  }

  const byStatus = {};
  assets.forEach((a) => {
    byStatus[a.status] = (byStatus[a.status] || 0) + 1;
  });

  const statusColor = {
    monitored: "var(--cyan)",
    attention: "var(--yellow)",
    high_risk: "var(--orange)",
    critical: "var(--red)",
    inactive: "var(--gray)",
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>Asset Health</h3>
        <span className="meta">{assets.length} ativos</span>
      </div>

      {assets.length === 0 && (
        <div className="state">Sem ativos observados — os valores aparecem
        só quando existirem dados reais.</div>
      )}

      {Object.entries(byStatus).map(([status, n]) => (
        <div className="health-row" key={status}>
          <span className="dot" style={{ background: statusColor[status] || "var(--gray)" }} />
          <span className="k">{status}</span>
          <span className="v">{n}</span>
        </div>
      ))}
    </div>
  );
}

export function ActivityFeed({ activity }) {
  return (
    <div className="panel area-activity">
      <div className="panel-head">
        <h3>Activity Monitoring</h3>
      </div>

      {!activity && <div className="state">a carregar…</div>}

      {activity && activity.length === 0 && (
        <div className="state">Sem atividade registada.</div>
      )}

      {(activity || []).slice(0, 8).map((item, i) => (
        <div className={`activity-item ${item.type}`} key={i}>
          {item.type === "job" ? "⚙" : "⚠"} {item.summary}
          <span className="stamp">{timeAgo(item.timestamp)}</span>
        </div>
      ))}
    </div>
  );
}
