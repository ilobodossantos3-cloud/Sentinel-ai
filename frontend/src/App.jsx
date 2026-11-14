import { useEffect, useState } from "react";
import TopBar from "./components/TopBar.jsx";
import Sidebar from "./components/Sidebar.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import ThreatsPage from "./pages/ThreatsPage.jsx";
import AssetsPage from "./pages/AssetsPage.jsx";
import AuditsPage from "./pages/AuditsPage.jsx";
import VulnerabilitiesPage from "./pages/VulnerabilitiesPage.jsx";

// Rotas ainda sem implementação real (nunca dados falsos).
const PLACEHOLDERS = {
  network: { phase: "Fase 5", text: "Monitorização de rede detalhada e correlação de eventos." },
  logs: { phase: "Fase 5", text: "Consulta e correlação de logs." },
  reports: { phase: "Fase 2", text: "Relatórios técnicos centralizados, com exportação e comparação de auditorias." },
  skills: { phase: "Fase 4", text: "Sistema modular de skills com permissões, âmbito e histórico de execução." },
  admin: { phase: "Fase 6", text: "Gestão de organizações, utilizadores, funções e permissões." },
};

function Placeholder({ route }) {
  const info = PLACEHOLDERS[route];
  return (
    <div className="placeholder">
      <div>
        <h2 style={{ margin: "0 0 6px", textTransform: "capitalize" }}>{route}</h2>
        <p style={{ color: "var(--text-faint)", maxWidth: 480 }}>{info.text}</p>
        <span className="tag">CHEGA NA {info.phase}</span>
      </div>
    </div>
  );
}

export default function App() {
  const [route, setRoute] = useState(
    window.location.hash.replace("#/", "") || "dashboard"
  );

  useEffect(() => {
    const onHash = () =>
      setRoute(window.location.hash.replace("#/", "") || "dashboard");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = (id) => {
    window.location.hash = `#/${id}`;
    setRoute(id);
  };

  const page =
    route === "dashboard" ? <DashboardPage />
    : route === "threats" ? <ThreatsPage />
    : route === "assets" ? <AssetsPage />
    : route === "audits" ? <AuditsPage />
    : route === "vulnerabilities" ? <VulnerabilitiesPage />
    : PLACEHOLDERS[route] ? <Placeholder route={route} />
    : <DashboardPage />;

  return (
    <div className="app-shell">
      <TopBar onBell={() => navigate("threats")} />
      <Sidebar current={route} onNavigate={navigate} />
      <main className="main">{page}</main>
    </div>
  );
}
