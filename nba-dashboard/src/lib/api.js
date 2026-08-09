// src/lib/api.js
import axios from 'axios';

const VITE_ENV = import.meta.env || {};

const DEFAULT_BASE = VITE_ENV.PROD
  ? 'https://hanson-hoops.onrender.com'     // prod default
  : 'http://localhost:8000';                // dev default

export const API_BASE = (VITE_ENV.VITE_API_BASE?.trim()) || DEFAULT_BASE;

export const api = axios.create({
  baseURL: API_BASE,
  // Global timeout for normal endpoints; heavy fit calls can override per-request.
  timeout: 45000,
});

const inFlightGets = new Map();

function sharedGetKey(url, config) {
  const params = Object.entries(config?.params || {}).sort(([a], [b]) => a.localeCompare(b));
  return JSON.stringify([url, params]);
}

// React StrictMode intentionally remounts effects in development. Coalesce
// identical GETs so that behavior does not double NBA-bound backend work.
export function sharedGet(url, config = {}) {
  const key = sharedGetKey(url, config);
  const existing = inFlightGets.get(key);
  if (existing) return existing;

  const request = api.get(url, config);
  inFlightGets.set(key, request);
  const clear = () => {
    if (inFlightGets.get(key) === request) inFlightGets.delete(key);
  };
  request.then(clear, clear);
  return request;
}

export function apiErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (detail && typeof detail.message === 'string' && detail.message.trim()) {
    const requestSuffix = detail.request_id ? ` (request ${detail.request_id})` : '';
    return `${detail.message}${requestSuffix}`;
  }
  return fallback;
}

// (optional) small logger
api.interceptors.response.use(
  r => r,
  err => {
    // Request cancellation is intentional in several components (AbortController).
    if (err?.code === 'ERR_CANCELED') {
      return Promise.reject(err);
    }
    const method = (err?.config?.method || 'get').toUpperCase();
    const url = err?.config?.url || 'unknown-url';
    console.error('[API]', method, url, err?.response?.status, err?.message);
    return Promise.reject(err);
  }
);
