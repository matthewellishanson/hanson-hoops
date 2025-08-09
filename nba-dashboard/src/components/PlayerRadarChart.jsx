import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import axios from 'axios';

function PlayerRadarChart({ playerId, season, playerName }) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    async function fetchStats() {
      try {
        const response = await axios.get('http://localhost:8000/player_profile_stats', {
          params: { player_id: playerId, season: season },
        });
        console.log("DEBUG: API response", response.data);  // 👈 add this
        setStats(response.data);
      } catch (error) {
        console.error('Error fetching player stats:', error);
      }
    }

    fetchStats();
  }, [playerId, season]);


  if (!stats) return <p>Loading chart...</p>;

  // Handle case where stats might be empty or zero
  if (
    stats.points === 0 &&
    stats.rebounds === 0 &&
    stats.assists === 0 &&
    stats.blocks === 0 &&
    stats.steals === 0
  ) {
  return <div>No data available for this player in {season}</div>;
}


    const values = [
      stats.points,
      stats.rebounds,
      stats.assists,
      stats.blocks,
      stats.steals,
      stats.fg_pct,
      stats.fg3_pct,
    ];

    const hoverText = [
      `Points: ${stats.raw_points} PPG`,
      `Rebounds: ${stats.raw_rebounds} RPG`,
      `Assists: ${stats.raw_assists} APG`,
      `Blocks: ${stats.raw_blocks} BPG`,
      `Steals: ${stats.raw_steals} SPG`,
      `FG%: ${stats.raw_fg_pct}%`,
      `3P%: ${stats.raw_fg3_pct}%`
    ];

  return (
    <Plot
      data={[{
        type: 'scatterpolar',
        r: values,
        theta: ['Points', 'Rebounds', 'Assists', 'Blocks', 'Steals', 'FG%', '3P%'],
        fill: 'toself',
        text: hoverText,
        hoverinfo: 'text', // show only the tooltip text
      }]}
      layout={{
        title: `${playerName} Profile`,
        polar: { radialaxis: { visible: true, range: [0, 100] } },
        margin: { t: 30, l: 30, r: 30, b: 30 },
      }}
      style={{ width: '100%', height: '100%' }}
      useResizeHandler={true}
      config={{ responsive: true }}
    />
  );

}

export default PlayerRadarChart;
