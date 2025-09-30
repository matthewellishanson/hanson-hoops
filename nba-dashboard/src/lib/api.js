import axios from 'axios';

const API_BASE =
  import.meta.env.MODE === 'development'
    ? 'http://localhost:8000'
    : 'https://hanson-hoops.onrender.com';

export const api = axios.create({
  baseURL: 'https://hanson-hoops.onrender.com',
  timeout: 45000,
  withCredentials: false,
});