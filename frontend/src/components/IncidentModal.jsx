import {
  deleteIncident,
  generateAnalysis,
  getIncidentAnalysis,
  getIncidentIntel,
  patchIncidentStatus,
} from "../services/api";
import { useEffect, useState } from "react";

/**
 * Incident detail modal: real data + AI analysis + lifecycle actions
 * + threat-intel feed matches (real feeds only).
 */
export default function IncidentModal({ incident, onClose, onChanged }) {
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [analysisError, setAnalysisError] = useState(false);
  const [intelMatches, setIntelMatches] = useState(null);
  const [acting, setActing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setAnalysis(null);
    setAnalysisError(false);
    setAnalysisLoading(true);
    setIntelMatches(null);

    getIncidentAnalysis(incident.id)
      .then((data) => { if (!cancelled) setAnalysis(data); })
      .catch((err) => {
        // 404 = analysis still generating in background (not an error state)
        if (!cancelled) setAnalysisError(err?.response?.status !== 404);
      })
      .finally(() => { if (!cancelled) setAnalysisLoading(false); });

    getIncidentIntel(incident.id)
      .then((data) => { if (!cancelled) setIntelMatches(data.matches); })
      .catch(() => { if (!cancelled) setIntelMatches([]); });

    return () => { cancelled = true; };
  }, [incident.id]);

  const regenerate = async () => {
    setActing(true);
    try {
      const data = await generateAnalysis(incident.id);
      setAnalysis(data);
      setAnalysisError(false);
    } catch {
      setAnalysisError(true);
    } finally {
      setActing(false);
    }
  };

  const setStatus = async (status) => {
    setActing(true);
    try {
      await patchIncidentStatus(incident.id, status);
      onChanged?.();
      onClose();
    } catch {
      setActing(false);
    }
  };

  const threatClass = (level) =>
    `sev ${String(level || "").toUpperCase()}`;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <span className={`sev ${incident.severity}`}>{incident.severity}</span>
            <h2>{incident.event_type}</h2>
            <span className="muted">
              Incidente #{incident.id} · {new Date(incident.created_at).toLocaleString()}
            </span>
          </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <button
                  title="Apagar incidente"
                  onClick={async () => {
                    if (!window.confirm(`Apagar incidente #${incident.id} e as suas análises?`)) return;
                    setActing(true);
                    try {
                      await deleteIncident(incident.id);
                      onChanged?.();
                      onClose();
                    } finally {
                      setActing(false);
                    }
                  }}
                  style={{ fontSize: 11, padding: "4px 10px" }}
                >
                  🗑
                </button>
                <button className="close-x" onClick={onClose}>✕</button>
              </div>
        </div>

        <div className="kv">
          <div><span>Origem</span><b>{incident.source_ip}{incident.source_port ? `:${incident.source_port}` : ""}</b></div>
          <div><span>Destino</span><b>{incident.destination_ip || "—"}{incident.destination_port ? `:${incident.destination_port}` : ""}</b></div>
          <div><span>Protocolo</span><b>{incident.protocol || "—"}</b></div>
          <div><span>Estado</span><b>{incident.status}</b></div>
        </div>

        {incident.description && (
          <p className="muted">{incident.description}</p>
        )}

        {intelMatches && intelMatches.length > 0 && (
          <div style={{
            border: "1px solid rgba(239,68,68,.35)",
            borderRadius: 8,
            padding: "10px 12px",
            margin: "10px 0",
            background: "rgba(239,68,68,.06)",
          }}>
            <b style={{ fontSize: 11.5, color: "var(--red)" }}>
              ⚠ Corresponde a feeds de threat intelligence
            </b>
            {intelMatches.map((m, i) => (
              <div className="ioc" key={i}>
                <span className="t">{m.category}</span>
                <span className="v">{m.ip} — {m.source}</span>
                <span className="when">feed</span>
              </div>
            ))}
          </div>
        )}

        <div className="actions-row">
          <span className="muted" style={{ alignSelf: "center" }}>Investigação:</span>
          <button disabled={acting || incident.status === "investigating"} onClick={() => setStatus("investigating")}>Marcar em investigação</button>
          <button disabled={acting || incident.status === "confirmed"} onClick={() => setStatus("confirmed")}>Confirmar incidente</button>
          <button disabled={acting || incident.status === "false_positive"} onClick={() => setStatus("false_positive")}>Falso positivo</button>
          <button disabled={acting || incident.status === "closed"} onClick={() => setStatus("closed")}>Fechar</button>
        </div>

        <div className="analysis-block">
          <h4>🤖 Análise SentinelAI</h4>

          {analysisLoading && <div className="state">A carregar análise…</div>}

          {!analysisLoading && analysis && (
            <>
              <div className="metrics">
                <span>Threat level <b className={threatClass(analysis.threat_level)}>{analysis.threat_level}</b></span>
                <span>Risk score <b>{analysis.risk_score}/100</b></span>
                <span>Confidence <b>{Math.round(analysis.confidence * 100)}%</b></span>
              </div>
              <p><b>{analysis.classification}</b></p>
              <p>{analysis.analysis}</p>

              {Array.isArray(analysis.indicators) && analysis.indicators.length > 0 && (
                <>
                  <h4>Indicadores</h4>
                  {analysis.indicators.map((ind, i) => (
                    <div className="ioc" key={i}>
                      <span className="t">{ind.type || "ioc"}</span>
                      <span className="v">{ind.value || String(ind)}</span>
                    </div>
                  ))}
                </>
              )}

              {Array.isArray(analysis.recommended_actions) && analysis.recommended_actions.length > 0 && (
                <>
                  <h4>Ações recomendadas</h4>
                  <ol>{analysis.recommended_actions.map((a, i) => <li key={i}>{typeof a === "string" ? a : JSON.stringify(a)}</li>)}</ol>
                </>
              )}
            </>
          )}

          {!analysisLoading && !analysis && (
            <div className="state">
              {analysisError
                ? "Não foi possível obter a análise."
                : "A análise IA ainda está a ser gerada em background."}
              <div className="actions-row">
                <button className="primary" disabled={acting} onClick={regenerate}>
                  {acting ? "a gerar…" : "⟳ Gerar análise agora"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
