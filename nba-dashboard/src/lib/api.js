// src/lib/api.js
import axios from 'axios';

const DEFAULT_BASE = import.meta.env.PROD
  ? 'https://hanson-hoops.onrender.com'     // prod default
  : 'http://localhost:8000';                // dev default

export const API_BASE = (import.meta.env.VITE_API_BASE?.trim()) || DEFAULT_BASE;

export const api = axios.create({
  baseURL: API_BASE,
  // Global timeout for normal endpoints; heavy fit calls can override per-request.
  timeout: 45000,
});

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
