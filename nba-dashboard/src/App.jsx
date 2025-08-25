import React, { useState } from 'react';
import PlayerDashboard from './pages/PlayerDashboard';

function currentNbaSeasonLabel() {
  const now = new Date();
  const start = now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1; // Sep=8-based
  const endYY = String((start + 1) % 100).padStart(2, '0');
  return `${start}-${endYY}`;
}

export default function App() {
  const [selectedPlayers, setSelectedPlayers] = useState([
    { playerId: '2544', playerName: 'LeBron James', season: '2023-24' },
  ]);
  const [showSelectorIndex, setShowSelectorIndex] = useState(null);
  // good default to use across the app (UI label can differ)
  const DEFAULT_SEASON = currentNbaSeasonLabel();

  // When user selects a player in the selector:
  const updatePlayer = (idx, player) => {
  setSelectedPlayers(prev => {
    const next = [...prev];
    next[idx] = {
      playerId: player.id,
      playerName: player.name,
      // Prefer the season chosen in the selector; if somehow missing, use current season.
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
      // open selector for the new slot
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
