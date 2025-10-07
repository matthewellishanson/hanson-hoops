// src/lib/api.js
import axios from "axios";

const isDev = import.meta.env.MODE === "development";

// Priority:
// 1) VITE_API_BASE (explicit override)
// 2) dev -> "/api" (Vite proxy), prod -> Render URL
export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (isDev ? "/api" : "https://hanson-hoops.onrender.com");

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 45000,
  withCredentials: false,
});

// Dev guardrail: warn if any request uses an absolute URL (bypasses baseURL)
if (isDev) {
  api.interceptors.request.use((cfg) => {
    const u = String(cfg.url || "");
    if (/^https?:\/\//i.test(u)) {
      console.warn("[API] Absolute URL bypass detected:", u);
    }
    return cfg;
  });
}

console.info("API_BASE ->", API_BASE);
