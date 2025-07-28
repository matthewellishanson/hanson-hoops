// pages/PlayerDashboard.jsx
import PlayerCard from '../components/PlayerCard';

export default function PlayerDashboard() {
  return (
    <div className="flex flex-wrap gap-4 justify-center">
      <PlayerCard playerId="2544" playerName="LeBron James" />
      <PlayerCard playerId="201939" playerName="Stephen Curry" />
      {/* Add more PlayerCards as needed */}
    </div>
  );
}
