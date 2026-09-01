import axios from "axios";

export const apiClient = axios.create({
  baseURL: "/api/asset-pipeline",
  headers: { "Content-Type": "application/json" },
});
