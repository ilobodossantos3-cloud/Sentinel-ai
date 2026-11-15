import { useState } from "react";
import {
  auditAssetNow,
  deleteAsset,
  getAssetDetail,
  getAssets,
  registerAsset,
} from "../services/api";
import { usePolling, timeAgo } from "../hooks";

const STATUS_COLOR = {
  monitored: "var(--cyan)",
  attention: "var(--yellow)",
  high_risk: "var(--orange)",
  critical: "var(--red)",
  inactive: "var(--gray)",
};

export default function AssetsPage() {
  const [assets, setAssets] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [form, setForm] = useState({ ip: "", name: "", asset_type: "server" });
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  const refresh = () =>
    getAssets().then(setAssets).catch(() => setAssets([]));

  usePolling(refresh, 10000);

  const analyze = async (ip) => {
    setNotice(null);
    try {
      const res = await auditAssetNow(ip);
      setNotice(`Análise #${res.audit_id} lançada para ${ip} (${res.target_url}). Vê-a na rota Audits.`);
    } catch (err) {
      const msg = err?.response?.data?.detail;
      setNotice(
        typeof msg === "string"
          ? msg
          : `Não foi possível lançar a análise para ${ip}.`
      );
    }
  };

  const remove = async (ip) => {
    if (!window.confirm(`Remover o ativo ${ip} do inventário?`)) return;
    setNotice(null);
    try {
      await deleteAsset(ip);
      setNotice(`Ativo ${ip} removido. O histórico de incidentes foi preservado.`);
      refresh();
    } catch {
      setNotice(`Não foi possível remover ${ip}.`);
    }
  };

  const open = async (ip) => {
    setSelected(ip);
    setDetail(null);
    try {
      setDetail(await getAssetDetail(ip));
    } catch {
      setDetail({ error: true });
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.ip) return;
    setSaving(true);
    try {
      await registerAsset(form);
      setForm({ ip: "", name: "", asset_type: "server" });
      refresh();
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Assets</h2>
          <span className="sub">
            Inventário alimentado por observações reais + registo manual
          </span>
        </div>
      </div>

      {notice && (
        <div className="panel" style={{ marginBottom: 14 }}>
          <div className="state" style={{ margin: 0 }}>{notice}</div>
        </div>
      )}

      <div className="panel" style={{ marginBottom: 14 }}>
        <form onSubmit={submit} className="filters" style={{ alignItems: "center" }}>          <input
            placeholder="Endereço IP (ex.: 10.10.10.10)"
            value={form.ip}
            onChange={(e) => setForm({ ...form, ip: e.target.value })}
            style={{
              background: "rgba(6,12,22,.8)",
              border: "1px solid var(--panel-border-soft)",
              color: "var(--text)",
              borderRadius: 8,
              padding: "8px 10px",
              fontSize: 12.5,
              minWidth: 220,
            }}
          />
          <input
            placeholder="Nome (opcional)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            style={{
              background: "rgba(6,12,22,.8)",
              border: "1px solid var(--panel-border-soft)",
              color: "var(--text)",
              borderRadius: 8,
              padding: "8px 10px",
              fontSize: 12.5,
            }}
          />
          <select
            value={form.asset_type}
            onChange={(e) => setForm({ ...form, asset_type: e.target.value })}
            style={{
              background: "#081019",
              border: "1px solid var(--panel-border-soft)",
              color: "var(--text)",
              borderRadius: 8,
              padding: "8px 10px",
              fontSize: 12.5,
            }}
          >
            {["server", "endpoint", "firewall", "router", "gateway", "iot", "application", "user"].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <button className="active" disabled={saving || !form.ip}>
            {saving ? "a registar…" : "+ Registar ativo"}
          </button>
        </form>
      </div>

      <div className="panel">
        {!assets && <div className="state">a carregar…</div>}

        {assets && assets.length === 0 && (
          <div className="state">
            Sem ativos ainda. Corre o ingester do Suricata ou
            regista um ativo manualmente acima.
          </div>
        )}

        {assets && assets.length > 0 && (
          <table className="data">
            <thead>
              <tr>
                <th>Estado</th>
                <th>IP</th>
                <th>Nome</th>
                <th>Tipo</th>
                <th>Incidentes abertos</th>
                <th>Visto</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <tr className="clickable" key={asset.ip} onClick={() => open(asset.ip)}>
                  <td>
                    <span className="dot" style={{ background: STATUS_COLOR[asset.status], display: "inline-block" }} />
                    {" "}{asset.status}
                  </td>
                  <td>{asset.ip}</td>
                  <td>{asset.name || "—"}</td>
                  <td>{asset.asset_type}</td>
                  <td>{asset.open_incidents}</td>
                  <td>{timeAgo(asset.last_seen_at)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <span style={{ display: "flex", gap: 4 }}>
                      <button
                        title="Análise de segurança agora"
                        onClick={() => analyze(asset.ip)}
                        style={{ fontSize: 10, padding: "3px 8px" }}
                      >
                        ⚡ Analisar
                      </button>
                      <button
                        title="Remover do inventário"
                        onClick={() => remove(asset.ip)}
                        style={{ fontSize: 10, padding: "3px 8px" }}
                      >
                        🗑
                      </button>
                    </span>
                  </td>
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
                <h2>{detail?.name || selected}</h2>
                <span className="muted">{selected}</span>
              </div>
              <button className="close-x" onClick={() => setSelected(null)}>✕</button>
            </div>

            {!detail && <div className="state">a carregar…</div>}
            {detail?.error && <div className="state error">Erro ao obter detalhe.</div>}

            {detail && !detail.error && (
              <>
                <div className="kv">
                  <div><span>Estado</span><b>{detail.status}</b></div>
                  <div><span>Tipo</span><b>{detail.asset_type}</b></div>
                  <div><span>SO</span><b>{detail.os_name || "—"}</b></div>
                  <div><span>Incidentes abertos</span><b>{detail.open_incidents}</b></div>
                  <div><span>Visto</span><b>{timeAgo(detail.last_seen_at)} atrás</b></div>
                  <div>
                    <span>URL de auditoria</span>
                    <b>{detail.audit_url || "— (sem serviço web detetado)"}</b>
                  </div>
                </div>

                {detail.recent_incidents?.map((inc) => (
                  <div className="list-item" key={inc.id}>
                    <span className={`sev ${inc.severity}`}>{inc.severity}</span>
                    {inc.event_type}
                    <span className="st">{inc.status}</span>
                    <span className="when">{timeAgo(inc.created_at)}</span>
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
