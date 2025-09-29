import React, { useState } from 'react';
import { HashRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import PlayerDashboard from './pages/PlayerDashboard';
import TeamDashboard from './pages/TeamDashboard.jsx';

// Navigation component
function Navigation() {
  const location = useLocation();
  
  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-primary mb-4">
      <div className="container">
        <Link className="navbar-brand" to="/">
          NBA Dashboard
        </Link>
        <div className="navbar-nav">
          <Link 
            className={`nav-link ${location.pathname === '/players' ? 'active' : ''}`} 
            to="/players"
          >
            Players
          </Link>
          <Link 
            className={`nav-link ${location.pathname === '/teams' ? 'active' : ''}`} 
            to="/teams"
          >
            Teams
          </Link>
        </div>
      </div>
    </nav>
  );
}

// Helper function for current NBA season
function currentNbaSeasonLabel() {
  const now = new Date();
  // Use October 15th as the season start date (same as other components)
  let start;
  if (now.getMonth() > 9 || (now.getMonth() === 9 && now.getDate() >= 15)) {
    start = now.getFullYear();
  } else {
    start = now.getFullYear() - 1;
  }
  const endYY = String((start + 1) % 100).padStart(2, '0');
  return `${start}-${endYY}`;
}

// Player Dashboard wrapper with state management
function PlayerDashboardWrapper() {
  const [selectedPlayers, setSelectedPlayers] = useState([
    { playerId: '2544', playerName: 'LeBron James', season: '2023-24' },
  ]);
  const [showSelectorIndex, setShowSelectorIndex] = useState(null);
  const DEFAULT_SEASON = currentNbaSeasonLabel();

  const updatePlayer = (idx, player) => {
    setSelectedPlayers(prev => {
      const next = [...prev];
      next[idx] = {
        playerId: player.id,
        playerName: player.name,
        season: player.season || DEFAULT_SEASON,
      };
      return next;
    });
    setShowSelectorIndex(null);
  };

  const removePlayer = (idx) => {
    setSelectedPlayers(prev => prev.filter((_, i) => i !== idx));
    setShowSelectorIndex(null);
  };

  const onAddPlayer = () => {
    setSelectedPlayers(prev => {
      if (prev.length >= 4) return prev;
      const next = [...prev, { playerId: '', playerName: '', season: DEFAULT_SEASON }];
      setShowSelectorIndex(next.length - 1);
      return next;
    });
  };

  return (
    <PlayerDashboard
      selectedPlayers={selectedPlayers}
      showSelectorIndex={showSelectorIndex}
      setShowSelectorIndex={setShowSelectorIndex}
      updatePlayer={updatePlayer}
      removePlayer={removePlayer}
      onAddPlayer={onAddPlayer}
    />
  );
}

// Main App component with routing
export default function App() {
  return (
    <Router>
      <div className="min-vh-100 bg-light">
        <Navigation />
        <Routes>
          <Route path="/" element={<PlayerDashboardWrapper />} />
          <Route path="/players" element={<PlayerDashboardWrapper />} />
          <Route path="/teams" element={<TeamDashboard />} />
        </Routes>
      </div>
    </Router>
  );
}
