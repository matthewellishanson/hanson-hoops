// src/components/PlayerSelector.jsx
import React, { useEffect, useState } from 'react';
import axios from 'axios';

export default function PlayerSelector({ onSelect }) {
  const [players, setPlayers] = useState([]);
  const [selectedPlayer, setSelectedPlayer] = useState('');
  const [season, setSeason] = useState('2023');

  useEffect(() => {
    axios.get('http://localhost:8000/players')
      .then(res => setPlayers(res.data))
      .catch(err => console.error('Error fetching players:', err));
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    const player = players.find(p => p.id === selectedPlayer);
    if (player) {
      onSelect({ playerId: selectedPlayer, playerName: player.name, season });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <select 
        value={selectedPlayer} 
        onChange={(e) => setSelectedPlayer(e.target.value)} 
        required
      >
        <option value="">Select Player</option>
        {players.map(p => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>

      <input 
        type="text" 
        value={season} 
        onChange={(e) => setSeason(e.target.value)} 
        placeholder="Season (e.g. 2023)" 
        required
      />

      <button type="submit" className="bg-blue-500 text-white px-2 py-1 rounded">
        Add Player
      </button>
    </form>
  );
}
