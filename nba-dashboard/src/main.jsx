import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import 'bootstrap/dist/css/bootstrap.min.css';
import './global.css' // ✅ THIS IS REQUIRED
import { API_BASE } from "./lib/api";

console.info("API_BASE (main) ->", API_BASE);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)


