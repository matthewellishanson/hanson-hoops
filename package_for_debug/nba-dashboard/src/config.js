// One source of truth for the backend base URL
export const API_BASE =
  import.meta.env.MODE === 'development'
    ? 'http://localhost:8000'
    : 'https://hanson-hoops.onrender.com';