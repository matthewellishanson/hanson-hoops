import React from 'react';
import PlayerRadarChart from './PlayerRadarChart'; // Assuming you have this component

export default function PlayerCard({ playerId, playerName, season, onReplace }) {
  return (
    <div className="border p-4 rounded shadow w-full min-h-[300px] flex flex-col">
      <div className="flex justify-between mb-2">
        <h2 className="text-xl font-bold">{playerName}</h2>
        <button 
          onClick={onReplace} 
          className="text-blue-500 text-sm hover:underline"
        >
          Replace
        </button>
      </div>
      <div className="chart-container">
        <PlayerRadarChart 
          playerId={playerId} 
          season={season} 
          playerName={playerName} 
        />
      </div>
    </div>
  );
}
