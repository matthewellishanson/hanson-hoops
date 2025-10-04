import React, { useEffect, useState } from 'react';
import * as Plotly from 'plotly.js-dist-min';
import Plot from 'react-plotly.js';
import { api } from '../lib/api';

// Let react-plotly.js find Plotly on window
if (typeof window !== 'undefined' && !window.Plotly) {
  window.Plotly = Plotly;
}

export default function PlayerRadarChart({ playerId, season, playerName = 'Player' }) {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        if (!playerId) return;
        console.log('[Radar] fetching', { playerId, season });
        const { data } = await api.get('/player_profile_stats', {
          params: { player_id: playerId, season }
        });
        setStats(data);
        setError(null);
      } catch (e) {
        console.error(e);
        setStats(null);
        setError('Player data unavailable.');
      }
    })();
  }, [playerId, season]);

  if (!playerId) return <div>Select a player to see a chart.</div>;
  if (error) return <div>{error}</div>;
  if (!stats) return <div>Loading chart...</div>;

  // Normalized values (0–100) — now with FT Rate, FT%, and Turnovers (inverted: lower is better)
  const theta = ['Points', 'Rebounds', 'Assists', 'Blocks', 'Steals', 'FG%', '3P%', 'FT Rate', 'FT%', 'Turnovers (↓ better)'];
  const values = [
    stats.points, stats.rebounds, stats.assists,
    stats.blocks, stats.steals, stats.fg_pct, stats.fg3_pct,
    stats.ft_rate, stats.ft_pct, stats.turnovers
  ];

  const allFinite = values.every(v => Number.isFinite(v));
  if (!allFinite) return <div>Data unavailable for this selection.</div>;

  const hoverText = [
    `Points: ${stats.raw_points} PPG`,
    `Rebounds: ${stats.raw_rebounds} RPG`,
    `Assists: ${stats.raw_assists} APG`,
    `Blocks: ${stats.raw_blocks} BPG`,
    `Steals: ${stats.raw_steals} SPG`,
    `FG%: ${stats.raw_fg_pct}%`,
    `3P%: ${stats.raw_fg3_pct}%`,
    `FT Rate: ${stats.raw_ft_rate}%`,
    `FT%: ${stats.raw_ft_pct}%`,
    `Turnovers: ${stats.raw_tov} TOPG`,
  ];

  return (
    <Plot
      data={[{
        type: 'scatterpolar',
        r: values,
        theta,
        fill: 'toself',
        text: hoverText,
        hoverinfo: 'text',
        name: playerName
      }]}
      layout={{
        title: `${playerName} Profile`,
        polar: {
          radialaxis: {
            visible: true,
            range: [0, 100],
            tickvals: [0, 20, 40, 60, 80, 100]
          }
        },
        margin: { t: 24, l: 16, r: 16, b: 22 },
        autosize: true
      }}
      style={{ width: '100%', height: '100%' }}
      useResizeHandler
      config={{ responsive: true, displayModeBar: false }}
    />
  );
}
