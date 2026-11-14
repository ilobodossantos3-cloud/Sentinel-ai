import { useState } from "react";
import {
  getVulnerabilities,
  getVulnerabilityDetail,
  patchVulnerabilityStatus,
} from "../services/api";
import { usePolling, timeAgo } from "../hooks";

const SEV_COLOR = {
  CRITICAL: "var(--red)",
  HIGH: "var(--orange)",
  MEDIUM: "var(--yellow)",
  LOW: "var(--cyan)",
  INFORMATIONAL: "var(--gray)",
};

const inputStyle = {
  background: "rgba(6,12,22,.8)",
  border: "1px solid var(--panel-border-soft)",
  color: "var(--text)",
  borderRadius: 8,
  padding: "6px 10px",
  fontSize: 12,
};

export default function VulnerabilitiesPage() {
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState({ status: "", severity: "" });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);

  const refresh = () =>
    getVulnerabilities({
      status: filters.status || undefined,
      severity: filters.severity || undefined,
    })
      .then(setData)
      .catch(() => setData({ stats: {}, vulnerabilities: [] }));

  usePolling(refresh, 10000, [filters.status, filters.severity]);

  const open = async (vulnId) => {
    setSelected(vulnId);
    setDetail(null);
    try {
      setDetail(await getVulnerabilityDetail(vulnId));
    } catch {
      setDetail({ error: true });
    }
  };

  const mark = async (status) => {
    await patchVulnerabilityStatus(selected, status);
    setDetail(await getVulnerabilityDetail(selected));
    refresh();
  };

  const stats = data?.stats || {};

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Vulnerabilities</h2>
          <span className="sub">
            Inventário derivado dos achados reais das auditorias — sem CVEs
            inventados
          </span>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="kv">
          <div><span>Total</span><b>{stats.total ?? "—"}</b></div>
          <div>
            <span>Abertas</span>
            <b style={{ color: "var(--red)" }}>{stats.open ?? "—"}</b>
          </div>
          <div>
            <span>Corrigidas</span>
            <b style={{ color: "var(--green)" }}>{stats.fixed ?? "—"}</b>
          </div>
          <div>
            <span>Aceites</span>
            <b style={{ color: "var(--yellow)" }}>{stats.accepted ?? "—"}</b>
          </div>
          <div>
            <span>Não vistas na última auditoria</span>
            <b style={{ color: "var(--cyan)" }}>
              {stats.not_detected_in_latest ?? "—"}
            </b>
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="filters" style={{ alignItems: "center" }}>
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            style={{ background: "#081019", ...inputStyle }}
          >
            <option value="">Estado: todos</option>
            <option value="open">abertas</option>
            <option value="fixed">corrigidas</option>
            <option value="accepted">aceites</option>
          </select>
          <select
            value={filters.severity}
            onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
            style={{ background: "#081019", ...inputStyle }}
          >
            <option value="">Severidade: todas</option>
            {["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="panel">
        {!data && <div className="state">a carregar…</div>}

        {data && data.vulnerabilities?.length === 0 && (
          <div className="state">
            Sem vulnerabilidades no inventário. Lança auditorias na rota
            Audits — os achados alimentam esta lista.
          </div>
        )}

        {data && data.vulnerabilities?.length > 0 && (
          <table className="data">
            <thead>
              <tr>
                <th>ID</th>
                <th>Severidade</th>
                <th>Vulnerabilidade</th>
                <th>Alvo</th>
                <th>Estado</th>
                <th>Detecções</th>
                <th>Vista</th>
              </tr>
            </thead>
            <tbody>
              {data.vulnerabilities.map((v) => (
                <tr className="clickable" key={v.vuln_id} onClick={() => open(v.vuln_id)}>
                  <td className="muted">{v.vuln_id}</td>
                  <td>
                    <span className={`sev ${v.severity}`}>{v.severity}</span>
                  </td>
                  <td style={{ maxWidth: 340 }}>
                    {v.title}
                    {v.missing_in_latest_audit && (
                      <span
                        className="tag"
                        style={{ marginLeft: 8, fontSize: 9 }}
                        title="Não foi re-detectada na auditoria mais recente deste alvo"
                      >
                        NÃO VISTA NA ÚLTIMA
                      </span>
                    )}
                  </td>
                  <td className="muted" style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {v.target_url || `alvo ${v.target_id}`}
                  </td>
                  <td>
                    <span className={`st ${v.status}`}>{v.status}</span>
                  </td>
                  <td>{v.detected_in_audits?.length || 0}×</td>
                  <td>{v.last_seen ? timeAgo(v.last_seen) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2>{selected}</h2>
                <span className="muted">{detail?.title || ""}</span>
              </div>
              <button className="close-x" onClick={() => setSelected(null)}>✕</button>
            </div>

            {!detail && <div className="state">a carregar…</div>}
            {detail?.error && <div className="state error">Erro ao obter detalhe.</div>}

            {detail && !detail.error && (
              <>
                <div className="kv">
                  <div>
                    <span>Severidade</span>
                    <b style={{ color: SEV_COLOR[detail.severity] }}>{detail.severity}</b>
                  </div>
                  <div><span>Estado</span><b>{detail.status}</b></div>
                  <div><span>Categoria</span><b>{detail.category}</b></div>
                  <div><span>Primeira detecção</span><b>{detail.first_seen ? timeAgo(detail.first_seen) : "—"}</b></div>
                </div>

                <div style={{ display: "flex", gap: 6, margin: "0 0 12px" }}>
                  <button
                    className="active"
                    style={{ fontSize: 10.5, padding: "4px 10px" }}
                    disabled={detail.status === "open"}
                    onClick={() => mark("open")}
                  >
                    reabrir
                  </button>
                  <button
                    style={{ fontSize: 10.5, padding: "4px 10px" }}
                    disabled={detail.status === "fixed"}
                    onClick={() => mark("fixed")}
                  >
                    marcar corrigida
                  </button>
                  <button
                    style={{ fontSize: 10.5, padding: "4px 10px" }}
                    disabled={detail.status === "accepted"}
                    onClick={() => mark("accepted")}
                  >
                    marcar aceite
                  </button>
                </div>

                {detail.impact && (
                  <div className="muted" style={{ fontSize: 11.5, marginBottom: 6 }}>
                    <b style={{ color: "var(--text-dim)" }}>Impacto:</b> {detail.impact}
                  </div>
                )}
                {detail.recommendation && (
                  <div className="muted" style={{ fontSize: 11.5, marginBottom: 10 }}>
                    <b style={{ color: "var(--text-dim)" }}>Recomendação:</b> {detail.recommendation}
                  </div>
                )}

                <b style={{ fontSize: 12 }}>Histórico por auditoria</b>
                {detail.history?.map((h) => (
                  <div className="list-item" key={h.audit_id} style={{ display: "block" }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span className={`sev ${h.severity}`}>{h.severity}</span>
                      <b style={{ fontSize: 11.5 }}>Auditoria #{h.audit_id}</b>
                      <span className={`st ${h.status}`}>{h.status}</span>
                      <span className="when">{timeAgo(h.detected_at)}</span>
                    </div>
                    <pre
                      style={{
                        background: "rgba(6,12,22,.8)",
                        border: "1px solid var(--panel-border-soft)",
                        borderRadius: 6,
                        padding: "8px 10px",
                        fontSize: 10.5,
                        color: "var(--text-dim)",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                        margin: "8px 0 0",
                        maxHeight: 120,
                        overflow: "auto",
                      }}
                    >
{h.evidence}
                    </pre>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
