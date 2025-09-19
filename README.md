# Hanson Hoops 🏀

Starting an NBA blog centered around a real-time data dashboard with client-side interactivity and data visuals.  
This repo powers the central dashboard that will serve as the homepage.

---

## 🚀 Setup Instructions

### 🔹 Backend (FastAPI + Python)

From the project root (`hanson-hoops/`):

#### 1. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux (bash/zsh):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### 2. Install backend dependencies
```bash
pip install -r backend/requirements.txt
```

#### 3. Run the FastAPI server
```bash
uvicorn backend.app.main:app --reload
```

Backend will run on [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

### 🔹 Frontend (React + Vite)

From the `nba-dashboard/` folder:

#### 1. Install dependencies
```bash
npm install
```

#### 2. Start the dev server
```bash
npm run dev
```

Frontend will run on [http://localhost:5173](http://localhost:5173).

---

### 🔹 Running Both Together

- Start backend (`uvicorn`) in one terminal  
- Start frontend (`npm run dev`) in another  
- Open [http://localhost:5173](http://localhost:5173) to use the app (frontend talks to backend on port 8000).

---

## ⚠️ Troubleshooting

- **CORS errors** → Make sure FastAPI CORS middleware allows `http://localhost:5173`.  
- **Port conflicts** → If port 5173 or 8000 is in use, stop other processes or change the port:

  Backend:
  ```bash
  uvicorn backend.app.main:app --reload --port 8001
  ```

  Frontend:
  ```bash
  npm run dev -- --port 5174
  ```

- **Python issues** → Verify you’re inside the virtual environment (`.venv`) before running backend commands.  
- **NBA API changes** → Occasionally, `nba_api` endpoints change. If you get unexpected keyword errors, check the repo for updates.

---

## 📂 Project Structure

```text
hanson-hoops/
├─ README.md
├─ .gitignore
├─ package-lock.json
├─ structure.txt                # Source listing you shared
├─ test_season.js
│
├─ backend/
│  ├─ requirements.txt          # Python backend dependencies (FastAPI, nba_api, etc.)
│  └─ app/
│     ├─ __init__.py
│     ├─ main.py                # FastAPI entrypoint
│     │
│     ├─ api/
│     │  ├─ __init__.py
│     │  └─ endpoints/
│     │     ├─ __init__.py
│     │     ├─ players.py       # /players, /player_profile_stats, /player_stats
│     │     └─ teams.py         # /team_profile_stats (and related team endpoints)
│     │
│     ├─ models/
│     │  ├─ __init__.py
│     │  └─ schemas.py          # Pydantic models / response payloads
│     │
│     └─ services/              # (present; no files listed — future service layer)
│
├─ data/
│  ├─ clean_data.py
│  └─ pull_data.py
│
├─ frontend/
│  └─ src/
│     ├─ charts/                # (present; files not listed in the dump)
│     ├─ components/
│     │  ├─ layout.jsx
│     │  └─ PlayerStatsDashboard.jsx
│     ├─ hooks/                 # (present; files not listed)
│     └─ pages/
│        └─ DashboardPage.jsx
│  └─ public/                   # (present; files not listed)
│
└─ nba-dashboard/               # Vite React app (current active frontend)
   ├─ .gitignore
   ├─ README.md
   ├─ index.html
   ├─ package.json
   ├─ package-lock.json
   ├─ vite.config.js
   │
   ├─ public/
   │  └─ vite.svg
   │
   └─ src/
      ├─ App.css
      ├─ App.jsx
      ├─ global.css
      ├─ main.jsx
      ├─ PlayerCard.css
      ├─ PlayerDashboard.css
      │
      ├─ assets/
      │  └─ react.svg
      │
      ├─ components/
      │  ├─ PlayerCard.jsx
      │  ├─ PlayerRadarChart.jsx
      │  ├─ PlayerSelector.jsx
      │  ├─ ShotMap.jsx
      │  ├─ TeamCard.jsx
      │  ├─ TeamRadarChart.jsx
      │  ├─ TeamSelector.jsx
      │  └─ TeamShotMap.jsx
      │
      └─ pages/
         ├─ PlayerDashboard.jsx
         └─ TeamDashboard.jsx
```

---

## 🛠️ Development Notes

- **Backend:** Python 3.12.2, dependencies in `backend/requirements.txt`  
- **Frontend:** React 19 + Vite 7, dependencies in `nba-dashboard/package.json`  
- **Virtual environment:** `.venv/` at project root (ignored in git)  
- **Styling:** Bootstrap 5 + custom CSS  
- **Charts:** Plotly.js via `react-plotly.js`

---

## 📌 Roadmap

- ✅ Player dashboards (radar + trend charts)  
- ✅ Team dashboards (radar + shot maps)  
- ⏳ Add database layer for persistence (`sqlalchemy` scaffolded)  
- ⏳ More opponent stats integration (defensive radar profiles)  
- ⏳ Deployment scripts (Dockerfile, CI/CD)
