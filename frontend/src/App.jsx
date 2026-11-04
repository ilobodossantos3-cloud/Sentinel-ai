import { useEffect, useState } from "react";
import {
  getIncidents,
  getIncidentAnalysis,
} from "./services/api";
import "./App.css";

function App() {
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [error, setError] = useState("");

  const loadIncidents = async () => {
    try {
      setLoading(true);

      const data = await getIncidents();

      setIncidents(data);
      setError("");
    } catch (err) {
      console.error(err);
      setError("Não foi possível conectar ao SentinelAI API.");
    } finally {
      setLoading(false);
    }
  };

  const openIncident = async (incident) => {
    try {
      setSelectedIncident(incident);
      setAnalysis(null);
      setAnalysisLoading(true);

      const data = await getIncidentAnalysis(incident.id);

      setAnalysis(data);
      setError("");
    } catch (err) {
      console.error(err);

      if (err?.response?.status === 404) {
        // A análise corre em background no backend:
        // 404 = ainda não existe, não é um erro.
        setAnalysis(null);
      } else {
        setError(
          "Não foi possível carregar a análise da IA."
        );
      }
    } finally {
      setAnalysisLoading(false);
    }
  };

  const closeAnalysis = () => {
    setSelectedIncident(null);
    setAnalysis(null);
  };

  useEffect(() => {
    loadIncidents();
  }, []);

  const highCount = incidents.filter(
    (incident) => incident.severity === "HIGH"
  ).length;

  const mediumCount = incidents.filter(
    (incident) => incident.severity === "MEDIUM"
  ).length;

  const lowCount = incidents.filter(
    (incident) => incident.severity === "LOW"
  ).length;

  return (
    <div className="app">

      {/* HEADER */}

      <header className="header">

        <div>
          <h1>SentinelAI</h1>

          <p>
            AI-Powered Cybersecurity Platform
          </p>
        </div>

        <button onClick={loadIncidents}>
          ↻ Refresh
        </button>

      </header>


      <main>

        {/* STATISTICS */}

        <section className="stats">

          <div className="stat-card">
            <span>Total Incidents</span>
            <strong>{incidents.length}</strong>
          </div>

          <div className="stat-card high">
            <span>High Severity</span>
            <strong>{highCount}</strong>
          </div>

          <div className="stat-card medium">
            <span>Medium Severity</span>
            <strong>{mediumCount}</strong>
          </div>

          <div className="stat-card low">
            <span>Low Severity</span>
            <strong>{lowCount}</strong>
          </div>

        </section>


        {/* INCIDENTS */}

        <section className="incidents">

          <div className="section-header">

            <div>
              <h2>Security Incidents</h2>
              <span>
                {incidents.length} detected
              </span>
            </div>

          </div>


          {loading && (
            <div className="message">
              Loading incidents...
            </div>
          )}


          {error && (
            <div className="message error">
              {error}
            </div>
          )}


          {!loading &&
            !error &&
            incidents.length === 0 && (
              <div className="message">
                No security incidents detected.
              </div>
            )}


          <div className="incident-list">

            {incidents.map((incident) => (

              <div
                className="incident-card clickable"
                key={incident.id}
                onClick={() => openIncident(incident)}
              >

                <div className="incident-top">

                  <div>

                    <h3>
                      Incident #{incident.id}
                    </h3>

                    <p>
                      {incident.event_type}
                    </p>

                  </div>


                  <span
                    className={`severity ${incident.severity.toLowerCase()}`}
                  >
                    {incident.severity}
                  </span>

                </div>


                <div className="incident-details">

                  <div>
                    <span>Source</span>
                    <strong>
                      {incident.source_ip}
                    </strong>
                  </div>


                  <div>
                    <span>Destination</span>
                    <strong>
                      {incident.destination_ip}
                    </strong>
                  </div>


                  <div>
                    <span>Protocol</span>
                    <strong>
                      {incident.protocol || "N/A"}
                    </strong>
                  </div>


                  <div>
                    <span>Port</span>
                    <strong>
                      {incident.destination_port || "N/A"}
                    </strong>
                  </div>

                </div>


                <p className="description">
                  {incident.description}
                </p>


                <div className="view-analysis">
                  🤖 View AI Analysis →
                </div>

              </div>

            ))}

          </div>

        </section>

      </main>


      {/* AI ANALYSIS MODAL */}

      {selectedIncident && (

        <div className="modal-overlay">

          <div className="analysis-modal">

            <div className="analysis-header">

              <div>

                <span className="ai-label">
                  🤖 SENTINELAI AI ANALYSIS
                </span>

                <h2>
                  Incident #{selectedIncident.id}
                </h2>

                <p>
                  {selectedIncident.event_type}
                </p>

              </div>


              <button
                className="close-button"
                onClick={closeAnalysis}
              >
                ✕
              </button>

            </div>


            {analysisLoading && (

              <div className="analysis-loading">

                <div className="loader"></div>

                <p>
                  AI analysis is being loaded...
                </p>

              </div>

            )}


            {!analysisLoading && !analysis && (

              <div className="analysis-loading">

                <p>
                  AI analysis is still being generated.
                  Try again in a few seconds.
                </p>

                <button onClick={() => openIncident(selectedIncident)}>
                  ↻ Retry
                </button>

              </div>

            )}


            {!analysisLoading && analysis && (

              <div className="analysis-content">

                {/* THREAT SUMMARY */}

                <section className="analysis-summary">

                  <div className="analysis-box">

                    <span>Threat Level</span>

                    <strong
                      className={`threat-${String(
                        analysis.threat_level
                      ).toLowerCase()}`}
                    >
                      {analysis.threat_level}
                    </strong>

                  </div>


                  <div className="analysis-box">

                    <span>Risk Score</span>

                    <strong>
                      {analysis.risk_score}
                      <small>/100</small>
                    </strong>

                  </div>


                  <div className="analysis-box">

                    <span>Confidence</span>

                    <strong>
                      {Math.round(
                        analysis.confidence * 100
                      )}
                      %
                    </strong>

                  </div>

                </section>


                {/* CLASSIFICATION */}

                <section className="analysis-section">

                  <h3>
                    Classification
                  </h3>

                  <div className="classification">
                    {analysis.classification}
                  </div>

                </section>


                {/* ANALYSIS */}

                <section className="analysis-section">

                  <h3>
                    AI Assessment
                  </h3>

                  <div className="analysis-text">
                    {analysis.analysis}
                  </div>

                </section>


                {/* INDICATORS */}

                <section className="analysis-section">

                  <h3>
                    Indicators of Compromise
                  </h3>

                  <div className="indicator-list">

                    {Array.isArray(
                      analysis.indicators
                    ) ? (

                      analysis.indicators.map(
                        (indicator, index) => (

                          <div
                            className="indicator"
                            key={index}
                          >

                            {typeof indicator ===
                            "string" ? (
                              <span>
                                {indicator}
                              </span>
                            ) : (

                              <>
                                <strong>
                                  {indicator.type}
                                </strong>

                                <span>
                                  {indicator.value}
                                </span>

                                {indicator.context && (
                                  <p>
                                    {indicator.context}
                                  </p>
                                )}

                              </>

                            )}

                          </div>

                        )
                      )

                    ) : (

                      <div className="analysis-text">
                        {analysis.indicators}
                      </div>

                    )}

                  </div>

                </section>


                {/* RECOMMENDED ACTIONS */}

                <section className="analysis-section">

                  <h3>
                    Recommended Actions
                  </h3>

                  <ol className="actions-list">

                    {Array.isArray(
                      analysis.recommended_actions
                    ) ? (

                      analysis.recommended_actions.map(
                        (action, index) => (

                          <li key={index}>
                            {action}
                          </li>

                        )
                      )

                    ) : (

                      <li>
                        {analysis.recommended_actions}
                      </li>

                    )}

                  </ol>

                </section>

              </div>

            )}

          </div>

        </div>

      )}

    </div>
  );
}

export default App;