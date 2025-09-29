// Choose API base at runtime/build time
const PROD_API = "https://hanson-hoops.onrender.com";
const DEV_API  = "http://localhost:8000";

export const API_BASE =
  (import.meta as any).env?.VITE_API_BASE
  ?? (window.location.host.endsWith("github.io") ? PROD_API : DEV_API);