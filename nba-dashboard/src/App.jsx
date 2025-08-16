import React, { useState } from 'react';
import PlayerDashboard from './pages/PlayerDashboard';

export default function App() {
  const [selectedPlayers, setSelectedPlayers] = useState([
    { playerId: '2544', playerName: 'LeBron James', season: '2023-24' },
  ]);
  const [showSelectorIndex, setShowSelectorIndex] = useState(null);

  // Update the player information
  const updatePlayer = (idx, player) => {
  setSelectedPlayers(prev => {
    const next = [...prev];
    next[idx] = {
      playerId: player.id,
      playerName: player.name,
      season: player.season,   // ✅ use selected season
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
      const next = [...prev, { playerId: '', playerName: '', season: '2023-24' }];
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
