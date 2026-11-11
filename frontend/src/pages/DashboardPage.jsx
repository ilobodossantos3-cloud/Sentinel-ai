import { useState } from "react";
import {
  getAssets,
  getAlertStats,
  getActivity,
  getIncidents,
  getPosture,
  getThreatIntel,
  getTopology,
} from "../services/api";
import { usePolling } from "../hooks";
import TopologyPanel from "../components/TopologyPanel.jsx";
import IncidentModal from "../components/IncidentModal.jsx";
import {
  ActivityFeed,
  AlertOverview,
  AssetHealth,
  CriticalIncidents,
  SecurityPosture,
  ThreatIntelligence,
} from "../components/Panels.jsx";

export default function DashboardPage() {
  const [topology, setTopology] = useState(null);
  const [incidents, setIncidents] = useState(null);
  const [posture, setPosture] = useState(null);
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState(null);
  const [intel, setIntel] = useState(null);
  const [assets, setAssets] = useState(null);
  const [selected, setSelected] = useState(null);

  usePolling(async () => {
    const results = await Promise.allSettled([
      getTopology(),
      getIncidents({ limit: 100 }),
      getPosture(),
      getAlertStats(),
      getActivity(),
      getThreatIntel(),
      getAssets(),
    ]);
    const [t, i, p, s, a, th, as] = results;
    if (t.status === "fulfilled") setTopology(t.value);
    if (i.status === "fulfilled") setIncidents(i.value);
    if (p.status === "fulfilled") setPosture(p.value);
    if (s.status === "fulfilled") setStats(s.value);
    if (a.status === "fulfilled") setActivity(a.value);
    if (th.status === "fulfilled") setIntel(th.value);
    if (as.status === "fulfilled") setAssets(as.value);
  }, 10000);

  return (
    <>
      <div className="dashboard">
        <TopologyPanel topology={topology} />

        <CriticalIncidents
          incidents={incidents}
          loading={!incidents}
          onSelect={setSelected}
        />

        <SecurityPosture posture={posture} />

        <ActivityFeed activity={activity} />

        <div className="dash-bottom">
          <AlertOverview stats={stats} />
          <ThreatIntelligence intel={intel} />
          <AssetHealth assets={assets} />
        </div>
      </div>

      {selected && (
        <IncidentModal
          incident={selected}
          onClose={() => setSelected(null)}
          onChanged={() => setSelected(null)}
        />
      )}
    </>
  );
}
