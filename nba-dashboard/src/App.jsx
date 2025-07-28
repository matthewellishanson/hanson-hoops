import React from 'react';
import PlayerRadarChart from './components/PlayerRadarChart';

function App() {
  return (
    <div>
      <h1>Player Profile Radar Chart</h1>
      <PlayerRadarChart playerId="2544" season="2023" />
    </div>
  );
}

export default App;

