import axios from 'axios';

const API_BASE =
  import.meta.env.MODE === 'development'
    ? 'http://localhost:8000'
    : 'https://hanson-hoops.onrender.com';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000, // 60s to survive Render cold starts
});