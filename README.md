# hanson-hoops
Starting an NBA blog centered around a real-time data dashboard with client-side interactivity and data visuals. Will pair in the future with data-rich and interactive posts, but this is just the repo for the central dashboard that will serve as the homepage.

# 🏀 Hanson Hoops App — Checkpoint Summary

## **1️⃣ Project Structure**
### **Backend**
- **FastAPI** (with CORS enabled for `localhost:5173`)
- **Endpoints:**
  - `/players` → Returns list of active players (ID + name)  
  - `/player_profile_stats` → Returns normalized averages for radar chart (PTS, REB, AST, BLK, STL, FG%, 3P%)  
  - `/player_stats` → Returns game-by-game points (for line charts / trends)  
- **Season formatting:** `format_season(year)` ensures correct `YYYY-YY` for NBA API  
- **Stat normalization:** `normalize_stats()` scales values for radar chart visual proportions while preserving raw values for tooltips.

### **Frontend**
- **React + Vite** (no Tailwind)
- **Components:**
  - `PlayerRadarChart.jsx` → Displays radar chart using Plotly  
  - `PlayerCard.jsx` → Container for a player chart + selector  
  - `PlayerDashboard.jsx` → Holds multiple `PlayerCard`s in a responsive grid  
- **Default load:** 1 Player Card (`LeBron James` for season `2023-24`)
- **User functionality:**
  - Add up to **4 total players**  
  - Responsive layout:
    - 1–2 players in a single row  
    - 3–4 players arranged in 2×2 grid  

---

## **2️⃣ Current Status**
✅ **Backend**
- `/player_profile_stats` fetches averages for valid `player_id` + `season`  
- Normalization prevents FG% and 3P% from dwarfing other stats  
- Season formatting works

✅ **Frontend**
- Default card loads radar chart for LeBron (scaling/tooltips still need adjustment)  
- Adding players works (up to limit)  
- Grid layout partially responsive

⚠️ **Known Issues**
- **Radar chart layout:** Charts overflow card bounds  
- **Tooltip values:** Currently showing normalized values; should show raw averages  
- **Replacing players:** Works, but shows empty chart if no games in season (needs UX handling)  
- **CORS:** Intermittent issues (fixed for now but may need verification for production)

---

## **3️⃣ Next Steps**
1. **Radar Chart Fixes**
   - Show normalized chart visually
   - Display raw averages in hover tooltips
   - Adjust scaling so charts fit within card
2. **Layout Improvements**
   - Ensure 2×2 grid for 4 players
   - Empty “Add Player” card centers properly when fewer than 4 players
3. **User Interaction**
   - Player selector to replace default player
   - Graceful handling of “no data for season” (avoid blank chart)
4. **Team View (future)**
   - Add `/team_profile_stats` endpoint
   - Build team radar chart and team cards