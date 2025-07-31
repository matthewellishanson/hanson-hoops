import React, { useState } from 'react';
import PlayerCard from '../components/PlayerCard';
import PlayerSelector from '../components/PlayerSelector';
// import PlayerDashboard.css'; // Assuming you have a CSS file for styles
import '../PlayerDashboard.css'; // Adjust the path as necessary

export default function PlayerDashboard() {
  const [selectedPlayers, setSelectedPlayers] = useState([
    { playerId: '2544', playerName: 'LeBron James', season: '2023-24' },
  ]);
  const [showSelectorIndex, setShowSelectorIndex] = useState(null);

  const updatePlayer = (index, newPlayer) => {
    const updatedPlayers = [...selectedPlayers];
    updatedPlayers[index] = newPlayer;
    setSelectedPlayers(updatedPlayers);
    setShowSelectorIndex(null);
  };

  const addPlayer = (player) => {
    if (selectedPlayers.length < 4) {
      setSelectedPlayers([...selectedPlayers, player]);
      setShowSelectorIndex(null);
    }
  };

  const removePlayer = (index) => {
    const updatedPlayers = selectedPlayers.filter((_, i) => i !== index);
    setSelectedPlayers(updatedPlayers);
  };

  return (
    <div className={`player-dashboard ${selectedPlayers.length > 2 ? 'grid-2x2' : 'grid-1x2'}`}>
      
      {selectedPlayers.map((p, idx) => (
        <div key={idx} className="player-card-container">
          {selectedPlayers.length > 1 && (
            <button 
              onClick={() => removePlayer(idx)}
              className="remove-btn"
            >
              ✕
            </button>
          )}

          {showSelectorIndex === idx ? (
            <PlayerSelector onSelect={(player) => updatePlayer(idx, player)} />
          ) : (
            <PlayerCard 
              playerId={p.playerId} 
              playerName={p.playerName} 
              season={p.season} 
              onReplace={() => setShowSelectorIndex(idx)}
            />
          )}
        </div>
      ))}

      {selectedPlayers.length < 4 && (
        <div 
          onClick={() => setShowSelectorIndex(selectedPlayers.length)} 
          className="add-player-card"
        >
          {showSelectorIndex === selectedPlayers.length ? (
            <PlayerSelector onSelect={addPlayer} />
          ) : (
            <span>➕ Add Player</span>
          )}
        </div>
      )}
    </div>
  );
}
