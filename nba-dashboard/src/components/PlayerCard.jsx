// src/components/PlayerCard.jsx
import React from 'react';
import PlayerRadarChart from './PlayerRadarChart';

export default function PlayerCard({ playerId, playerName, season }) {
  return (
    <div className="border-2 border-blue-500 bg-gray-100 p-4 rounded shadow w-[400px] min-h-[400px]">
      <h2 className="text-xl font-bold mb-2">{playerName}</h2>
      <PlayerRadarChart playerId={playerId} season={season} />
    </div>
  );
}

