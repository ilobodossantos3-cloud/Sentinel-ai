import { useState } from "react";
import { createAudit, getAuditDetail, getAudits } from "../services/api";
import { usePolling, timeAgo } from "../hooks";

const AUDIT_STATUS = {
  pending: { color: "var(--gray)", label: "pendente" },
  running: { color: "var(--cyan)", label: "a correr" },
  completed: { color: "var(--green)", label: "concluída" },
  partial: { color: "var(--yellow)", label: "parcial" },
  failed: { color: "var(--red)", label: "falhada" },
};

const inputStyle = {
  background: "rgba(6,12,22,.8)",
  border: "1px solid var(--panel-border-soft)",
  color: "var(--text)",
  borderRadius: 8,
  padding: "8px 10px",
  fontSize: 12.5,
};

function scoreColor(score) {
  if (score == null) return "var(--gray)";
  if (score < 50) return "var(--red)";
  if (score < 80) return "var(--orange)";
  return "var(--green)";
}

export default function AuditsPage() {
  const [audits, setAudits] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [form, setForm] = useState({
    url: "",
    scope_note: "",
    authorized: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const refresh = () =>
    getAudits().then(setAudits).catch(() => setAudits([]));

  usePolling(refresh, 5000);

  const open = async (id) => {
    setSelected(id);
    setDetail(null);
    try {
      setDetail(await getAuditDetail(id));
    } catch {
      setDetail({ error: true });
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.url || !form.authorized) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await createAudit({
        url: form.url,
        authorized: form.authorized,
        scope_note: form.scope_note || null,
      });
      setForm({ url: "", scope_note: "", authorized: false });
      refresh();
    } catch (err) {
      const msg = err?.response?.data?.detail;
      setSubmitError(
        typeof msg === "string" ? msg : "Erro ao lançar a auditoria."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Auditorias</h2>
          <span className="sub">
            Verificações não destrutivas (só HTTP GET) em alvos autorizados
          </span>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <form onSubmit={submit} className="filters" style={{ alignItems: "center" }}>
          <input
            placeholder="Alvo (ex.: https://app.exemplo.com)"
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
            style={{ ...inputStyle, minWidth: 260 }}
          />
          <input
            placeholder="Âmbito / notas de autorização (opcional)"
            value={form.scope_note}
            onChange={(e) => setForm({ ...form, scope_note: e.target.value })}
            style={{ ...inputStyle, minWidth: 220 }}
          />
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11.5,
              color: "var(--text-dim)",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            <input
              type="checkbox"
              checked={form.authorized}
              onChange={(e) => setForm({ ...form, authorized: e.target.checked })}
              style={{ accentColor: "var(--cyan)" }}
            />
            Confirmo autorização para testar este alvo
          </label>
          <button className="active" disabled={submitting || !form.url || !form.authorized}>
            {submitting ? "a lançar…" : "+ Lançar auditoria"}
          </button>
        </form>

        {submitError && (
          <div className="state error" style={{ marginTop: 10 }}>{submitError}</div>
        )}
      </div>

      <div className="panel">
        {!audits && <div className="state">a carregar…</div>}

        {audits && audits.length === 0 && (
          <div className="state">
            Sem auditorias ainda. Lança a primeira contra um alvo
            que tenhas autorização para testar.
          </div>
        )}

        {audits && audits.length > 0 && (
          <table className="data">
            <thead>
              <tr>
                <th>#</th>
                <th>Alvo</th>
                <th>Estado</th>
                <th>Score</th>
                <th>Resumo</th>
                <th>Terminada</th>
              </tr>
            </thead>
            <tbody>
              {audits.map((a) => {
                const st = AUDIT_STATUS[a.status] || AUDIT_STATUS.pending;
                return (
                  <tr className="clickable" key={a.id} onClick={() => open(a.id)}>
                    <td>{a.id}</td>
                    <td>{a.target_id}</td>
                    <td>
                      <span className="dot" style={{ background: st.color, display: "inline-block" }} />
                      {" "}{st.label}
                    </td>
                    <td style={{ color: scoreColor(a.score), fontWeight: 600 }}>
                      {a.score ?? "—"}
                    </td>
                    <td className="muted" style={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {a.summary || "—"}
                    </td>
                    <td>{a.finished_at ? timeAgo(a.finished_at) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2>Auditoria #{selected}</h2>
                <span className="muted">{detail?.target_url || ""}</span>
              </div>
              <button className="close-x" onClick={() => setSelected(null)}>✕</button>
            </div>

            {!detail && <div className="state">a carregar…</div>}
            {detail?.error && <div className="state error">Erro ao obter detalhe.</div>}

            {detail && !detail.error && (
              <>
                <div className="kv">
                  <div><span>Estado</span><b>{AUDIT_STATUS[detail.status]?.label || detail.status}</b></div>
                  <div>
                    <span>Score</span>
                    <b style={{ color: scoreColor(detail.score) }}>{detail.score ?? "—"}</b>
                  </div>
                  <div><span>Início</span><b>{detail.started_at ? timeAgo(detail.started_at) : "—"}</b></div>
                  <div><span>Fim</span><b>{detail.finished_at ? timeAgo(detail.finished_at) : "—"}</b></div>
                </div>

                {detail.summary && (
                  <p className="muted" style={{ margin: "0 0 10px" }}>{detail.summary}</p>
                )}

                {detail.error && (
                  <div className="state error">{detail.error}</div>
                )}

                {detail.findings?.length === 0 && !detail.error && (
                  <div className="state">Sem achados nas verificações não destrutivas.</div>
                )}

                {detail.findings?.map((f) => (
                  <div className="list-item" key={f.id} style={{ display: "block" }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span className={`sev ${f.severity}`}>{f.severity}</span>
                      <b style={{ fontSize: 12.5 }}>{f.title}</b>
                      <span className="when">{f.category}</span>
                    </div>
                    <pre
                      style={{
                        background: "rgba(6,12,22,.8)",
                        border: "1px solid var(--panel-border-soft)",
                        borderRadius: 6,
                        padding: "8px 10px",
                        fontSize: 11,
                        color: "var(--text-dim)",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                        margin: "8px 0 6px",
                        maxHeight: 160,
                        overflow: "auto",
                      }}
                    >
{f.evidence}
                    </pre>
                    {f.impact && (
                      <div className="muted" style={{ fontSize: 11.5 }}>
                        <b style={{ color: "var(--text-dim)" }}>Impacto:</b> {f.impact}
                      </div>
                    )}
                    {f.recommendation && (
                      <div className="muted" style={{ fontSize: 11.5 }}>
                        <b style={{ color: "var(--text-dim)" }}>Recomendação:</b> {f.recommendation}
                      </div>
                    )}
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
