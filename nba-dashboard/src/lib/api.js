// src/lib/api.js
import axios from "axios";

// Prefer Vite env; fall back to current origin (for dev reverse proxy), then localhost
const API_BASE =
  import.meta.env.VITE_API_BASE ||
  (import.meta.env.MODE === 'development' ? '/api' : '') ||
  'http://localhost:8000';

console.log('API_BASE ->', API_BASE);

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
});
