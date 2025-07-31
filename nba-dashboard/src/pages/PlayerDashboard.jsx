// src/pages/PlayerDashboard.jsx
import React, { useState } from 'react';
import PlayerCard from '../components/PlayerCard';
import PlayerSelector from '../components/PlayerSelector';

export default function PlayerDashboard() {
  const [selectedPlayers, setSelectedPlayers] = useState([
    { playerId: '2544', playerName: 'LeBron James', season: '2023-24' }, // Default player
  ]);
  const [showSelector, setShowSelector] = useState(false);

  const addPlayer = (player) => {
    setSelectedPlayers([...selectedPlayers, player]);
    setShowSelector(false);
  };

  return (
    <div className="flex gap-4 p-4">
      {selectedPlayers.map((p, idx) => (
        <PlayerCard 
          key={idx} 
          playerId={p.playerId} 
          playerName={p.playerName} 
          season={p.season} 
        />
      ))}

      {/* Add Player Column */}
      <div 
        onClick={() => setShowSelector(true)} 
        className="flex items-center justify-center border-2 border-green-500 bg-gray-50 p-4 rounded shadow w-[400px] h-[400px] cursor-pointer hover:bg-green-100"
      >
        {showSelector ? (
          <PlayerSelector onSelect={addPlayer} />
        ) : (
        <span className="text-2xl font-bold text-green-600">➕ Add Player</span>
        )}
      </div>
    </div>
  );
}
