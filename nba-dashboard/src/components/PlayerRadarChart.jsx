import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import axios from 'axios';

function PlayerRadarChart({ playerId, season }) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    async function fetchStats() {
      try {
        const response = await axios.get('http://localhost:8000/player_profile_stats', {
          params: { player_id: playerId, season: season },
        });
        setStats(response.data);
      } catch (error) {
        console.error('Error fetching player stats:', error);
      }
    }

    fetchStats();
  }, [playerId, season]);

  if (!stats) return <p>Loading chart...</p>;

  const values = [
    stats.points,
    stats.rebounds,
    stats.assists,
    stats.blocks,
    stats.steals,
    stats.fg_pct,
    stats.fg3_pct,
  ];

  return (
    <Plot
      data={[
        {
          type: 'scatterpolar',
          r: values,
          theta: ['PTS', 'REB', 'AST', 'BLK', 'STL', 'FG%', '3P%'],
          fill: 'toself',
          name: `Player ${playerId}`,
        },
      ]}
      layout={{
        polar: {
          radialaxis: { visible: true, range: [0, Math.max(...values) + 5] },
        },
        showlegend: false,
        title: `Player ${playerId} Season ${season} Profile`,
      }}
    />
  );
}

export default PlayerRadarChart;
