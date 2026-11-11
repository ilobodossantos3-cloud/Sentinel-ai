import Icon from "./Icon.jsx";

const NAV = [
  { id: "dashboard", label: "Dashboard" },
  { id: "threats", label: "Threats" },
  { id: "assets", label: "Assets" },
  { id: "audits", label: "Audits", phase: "Fase 2" },
  { id: "vulnerabilities", label: "Vulnerabilities", phase: "Fase 2/3" },
  { id: "network", label: "Network", phase: "Fase 5" },
  { id: "logs", label: "Logs", phase: "Fase 5" },
  { id: "reports", label: "Reports", phase: "Fase 2" },
  { id: "skills", label: "Skills", phase: "Fase 4" },
  { id: "admin", label: "Admin", phase: "Fase 6" },
];

export default function Sidebar({ current, onNavigate }) {
  return (
    <nav className="sidebar">
      {NAV.map((item) => (
        <button
          key={item.id}
          className={`nav-item ${current === item.id ? "active" : ""}`}
          onClick={() => onNavigate(item.id)}
        >
          <Icon name={item.id} />
          {item.label}
          {item.phase && <span className="soon">{item.phase}</span>}
        </button>
      ))}
    </nav>
  );
}
