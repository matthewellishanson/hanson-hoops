// components/PlayerCard.jsx
import PlayerRadarChart from './PlayerRadarChart';

export default function PlayerCard({ playerId, playerName }) {
  return (
    <div className="border p-4 rounded shadow w-[400px]">
      <h2 className="text-xl font-bold mb-2">{playerName}</h2>
      <PlayerRadarChart playerId={playerId} />
    </div>
  );
}
