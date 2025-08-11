import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import axios from 'axios';

export default function PlayerRadarChart({ playerId, season, playerName = 'Player' }) {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    async function fetchStats() {
      try {
        setError(null);
        const res = await axios.get('http://localhost:8000/player_profile_stats', {
          params: { player_id: playerId, season }
        });
        if (active) setStats(res.data);
      } catch (e) {
        console.error('Error fetching player stats:', e);
        if (active) setError('Could not load stats');
      }
    }
    fetchStats();
    return () => { active = false; };
  }, [playerId, season]);

  if (error) return <div>{error}</div>;
  if (!stats) return <div>Loading chart...</div>;

  const values = [
    stats.points, stats.rebounds, stats.assists,
    stats.blocks, stats.steals, stats.fg_pct, stats.fg3_pct
  ];

  // guard against bad data
  const allFinite = values.every(v => Number.isFinite(v));
  if (!allFinite) return <div>Data unavailable for this selection.</div>;

  const theta = ['Points', 'Rebounds', 'Assists', 'Blocks', 'Steals', 'FG%', '3P%'];

  // raw values for tooltip
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
        r: values,          // normalized 0–100 for visual scale
        theta,              // category labels
        fill: 'toself',
        text: hoverText,    // show raw averages in tooltip
        hoverinfo: 'text',
        name: playerName
      }]}
      layout={{
        title: `${playerName} Profile`,
        polar: {
          radialaxis: {
            visible: true,
            range: [0, 100],                // keep charts comparable
            tickvals: [0, 20, 40, 60, 80, 100]
          }
        },
        margin: { t: 30, l: 30, r: 30, b: 30 },
        autosize: true
      }}
      style={{ width: '100%', height: '100%' }}
      useResizeHandler={true}
      config={{ responsive: true, displayModeBar: false }}
    />
  );
}
