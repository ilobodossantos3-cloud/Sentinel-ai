import { useState } from "react";
import { getIncidents } from "../services/api";
import { usePolling, timeAgo } from "../hooks";
import IncidentModal from "../components/IncidentModal.jsx";

const FILTERS = [
  { id: "all", label: "Todos" },
  { id: "new", label: "Novos" },
  { id: "investigating", label: "Em investigação" },
  { id: "confirmed", label: "Confirmados" },
  { id: "false_positive", label: "Falsos positivos" },
  { id: "closed", label: "Fechados" },
];

export default function ThreatsPage() {
  const [incidents, setIncidents] = useState(null);
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(null);

  usePolling(async () => {
    try {
      setIncidents(await getIncidents({ limit: 200 }));
    } catch {
      setIncidents([]);
    }
  }, 10000);

  const list = (incidents || []).filter(
    (i) => filter === "all" || i.status === filter
  );

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Threats</h2>
          <span className="sub">
            Deteções do Suricata com ciclo de vida de investigação
          </span>
        </div>
        <div className="filters">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              className={filter === f.id ? "active" : ""}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="panel">
        {!incidents && <div className="state">a carregar…</div>}

        {incidents && list.length === 0 && (
          <div className="state">Sem deteções neste filtro.</div>
        )}

        {incidents && list.length > 0 && (
          <table className="data">
            <thead>
              <tr>
                <th>Sev.</th>
                <th>Evento</th>
                <th>Origem</th>
                <th>Destino</th>
                <th>Estado</th>
                <th>Quando</th>
              </tr>
            </thead>
            <tbody>
              {list.map((incident) => (
                <tr
                  className="clickable"
                  key={incident.id}
                  onClick={() => setSelected(incident)}
                >
                  <td><span className={`sev ${incident.severity}`}>{incident.severity}</span></td>
                  <td>{incident.event_type}</td>
                  <td>{incident.source_ip}</td>
                  <td>{incident.destination_ip || "—"}</td>
                  <td><span className={`st ${incident.status}`}>{incident.status}</span></td>
                  <td>{timeAgo(incident.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <IncidentModal
          incident={selected}
          onClose={() => setSelected(null)}
          onChanged={() => {
            setSelected(null);
            getIncidents({ limit: 200 }).then(setIncidents).catch(() => {});
          }}
        />
      )}
    </>
  );
}
