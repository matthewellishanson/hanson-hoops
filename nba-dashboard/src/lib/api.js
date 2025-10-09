// src/lib/api.js
import axios from 'axios';

const DEFAULT_BASE = import.meta.env.PROD
  ? 'https://hanson-hoops.onrender.com'     // prod default
  : 'http://localhost:8000';                // dev default

export const API_BASE = (import.meta.env.VITE_API_BASE?.trim()) || DEFAULT_BASE;

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// (optional) small logger
api.interceptors.response.use(
  r => r,
  err => {
    console.error('[API]', err?.response?.status, err?.message);
    return Promise.reject(err);
  }
);
