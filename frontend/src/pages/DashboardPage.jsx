import { useState } from "react";
import {
  getAssets,
  getAlertStats,
  getActivity,
  getIncidents,
  getIntelFeeds,
  getPosture,
  getThreatIntel,
  getTopology,
  refreshIntelFeeds,
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
  const [feeds, setFeeds] = useState(null);
  const [refreshingFeeds, setRefreshingFeeds] = useState(false);
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
      getIntelFeeds(),
    ]);
    const [t, i, p, s, a, th, as, fd] = results;
    if (t.status === "fulfilled") setTopology(t.value);
    if (i.status === "fulfilled") setIncidents(i.value);
    if (p.status === "fulfilled") setPosture(p.value);
    if (s.status === "fulfilled") setStats(s.value);
    if (a.status === "fulfilled") setActivity(a.value);
    if (th.status === "fulfilled") setIntel(th.value);
    if (as.status === "fulfilled") setAssets(as.value);
    if (fd.status === "fulfilled") setFeeds(fd.value);
  }, 10000);

  const doRefreshFeeds = async () => {
    setRefreshingFeeds(true);
    try {
      await refreshIntelFeeds();
      // give the background job a moment, then reload feed status
      setTimeout(() => getIntelFeeds().then(setFeeds).catch(() => {}), 4000);
    } finally {
      setRefreshingFeeds(false);
    }
  };

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
          <ThreatIntelligence
            intel={intel}
            feeds={feeds}
            onRefresh={doRefreshFeeds}
            refreshing={refreshingFeeds}
          />
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
