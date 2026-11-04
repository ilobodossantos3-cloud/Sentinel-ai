import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

export const getIncidents = async () => {
  const response = await api.get("/incidents/");
  return response.data;
};

export const getIncidentAnalysis = async (incidentId) => {
  const response = await api.get(`/incidents/${incidentId}/analysis`);
  return response.data;
};

export default api;
