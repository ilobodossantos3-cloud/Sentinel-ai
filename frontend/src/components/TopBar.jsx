import { useState } from "react";
import { getAlertStats, getHealth } from "../services/api";
import { useClock, usePolling } from "../hooks";

export default function TopBar({ onBell }) {
  const clock = useClock();
  const [health, setHealth] = useState(null);
  const [openCritical, setOpenCritical] = useState(0);

  usePolling(async () => {
    try {
      setHealth(await getHealth());
    } catch {
      setHealth(null);
    }
  }, 8000);

  usePolling(async () => {
    try {
      const stats = await getAlertStats();
      setOpenCritical(
        (stats.open_by_severity?.CRITICAL || 0) +
        (stats.open_by_severity?.HIGH || 0)
      );
    } catch {
      setOpenCritical(0);
    }
  }, 10000);

  const state = !health
    ? { cls: "", label: "API a ligar…" }
    : health.status === "healthy"
      ? { cls: "ok", label: "Sistemas operacionais" }
      : { cls: "down", label: "Sistema degradado" };

  return (
    <header className="topbar">
      <div className="brand">
        <span className="shield">🛡</span>
        SENTINELAI
        <small>Security Operations Center</small>
      </div>

      <div className="spacer" />

      <div className="sys-state">
        <span className={`dot ${state.cls}`} />
        {state.label}
      </div>

      <button className="notif" onClick={onBell} title="Incidentes críticos/altos abertos">
        🔔
        {openCritical > 0 && <span className="badge">{openCritical}</span>}
      </button>

      <span className="clock">{clock}</span>
    </header>
  );
}
