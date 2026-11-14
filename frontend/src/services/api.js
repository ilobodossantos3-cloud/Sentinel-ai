import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
});

// system
export const getHealth = () =>
  api.get("/health").then((r) => r.data);

// incidents
export const getIncidents = (params) =>
  api.get("/incidents/", { params }).then((r) => r.data);

export const getIncidentAnalysis = (id) =>
  api.get(`/incidents/${id}/analysis`).then((r) => r.data);

export const generateAnalysis = (id) =>
  api.post(`/incidents/${id}/analysis`).then((r) => r.data);

export const patchIncidentStatus = (id, status) =>
  api.patch(`/incidents/${id}`, { status }).then((r) => r.data);

// assets
export const getAssets = () =>
  api.get("/assets/").then((r) => r.data);

export const getAssetDetail = (ip) =>
  api.get(`/assets/${ip}`).then((r) => r.data);

export const registerAsset = (data) =>
  api.post("/assets/", data).then((r) => r.data);

// audits
export const getAudits = () =>
  api.get("/audits/").then((r) => r.data);

export const getAuditDetail = (id) =>
  api.get(`/audits/${id}`).then((r) => r.data);

export const createAudit = (data) =>
  api.post("/audits/", data).then((r) => r.data);

export const getAuditReport = (id) =>
  api
    .get(`/audits/${id}/report`, {
      responseType: "text",
      transformResponse: [(d) => d],
    })
    .then((r) => r.data);

export const compareAudits = (a, b) =>
  api.get("/audits/compare", { params: { a, b } }).then((r) => r.data);

export const patchFindingStatus = (auditId, findingId, status) =>
  api
    .patch(`/audits/${auditId}/findings/${findingId}`, { status })
    .then((r) => r.data);

// dashboard
export const getTopology = () =>
  api.get("/topology").then((r) => r.data);

export const getPosture = () =>
  api.get("/posture").then((r) => r.data);

export const getAlertStats = () =>
  api.get("/stats/alerts").then((r) => r.data);

export const getActivity = () =>
  api.get("/activity").then((r) => r.data);

export const getThreatIntel = () =>
  api.get("/threat-intel").then((r) => r.data);

export default api;
