import React, { useEffect, useState } from 'react';
import * as Plotly from 'plotly.js-dist-min';
import Plot from 'react-plotly.js';
import { api } from '../lib/api';

const ACCENT = '#7c3aed';

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
        const { data } = await api.get('/player_profile_stats', {
          params: { player_id: playerId, season, scale: 'percentile' },
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

  const isFiniteNumber = (v) => typeof v === 'number' && Number.isFinite(v);
  const clamp01 = (v) => Math.max(0, Math.min(100, v ?? 0));

  const metricKeys = [
    'points', 'rebounds', 'assists', 'blocks', 'steals',
    'fg_pct', 'fg3_pct', 'ft_rate', 'ft_pct', 'turnovers',
  ];

  const hasAnyMetric = metricKeys.some((k) => isFiniteNumber(stats[k]));
  if (!hasAnyMetric) return <div>Data unavailable for this selection.</div>;

  const theta = [
    'Points', 'Rebounds', 'Assists', 'Blocks', 'Steals',
    'FG%', '3P%', 'FT Rate', 'FT%', 'Turnovers (↓ better)',
  ];

  const r = metricKeys.map((k) => clamp01(isFiniteNumber(stats[k]) ? stats[k] : 0));

  const hoverText = [
    `Points: ${stats.raw_points ?? '—'} PPG`,
    `Rebounds: ${stats.raw_rebounds ?? '—'} RPG`,
    `Assists: ${stats.raw_assists ?? '—'} APG`,
    `Blocks: ${stats.raw_blocks ?? '—'} BPG`,
    `Steals: ${stats.raw_steals ?? '—'} SPG`,
    `FG%: ${stats.raw_fg_pct ?? '—'}%`,
    `3P%: ${stats.raw_fg3_pct ?? '—'}%`,
    `FT Rate: ${stats.raw_ft_rate ?? '—'}%`,
    `FT%: ${stats.raw_ft_pct ?? '—'}%`,
    `Turnovers: ${stats.raw_tov ?? '—'} TOPG`,
  ];

  // Optional: hide completely flat shape
  if (r.every((v) => v === 0)) return <div>Data unavailable for this selection.</div>;

  // 🔒 Close the loop
  const rClosed = [...r, r[0]];
  const thetaClosed = [...theta, theta[0]];
  const hoverClosed = [...hoverText, hoverText[0]];

  return (
    <Plot
      data={[{
        type: 'scatterpolar',
        r: rClosed,
        theta: thetaClosed,
        fill: 'toself',
        text: hoverClosed,
        hoverinfo: 'text',
        name: playerName,
        line: { color: ACCENT },
        marker: { color: ACCENT },
        fillcolor: 'rgba(124,58,237,0.25)',
      }]}
      layout={{
        title: `${playerName} Profile`,
        polar: {
          radialaxis: {
            visible: true,
            range: [0, 100],
            tickvals: [0, 20, 40, 60, 80, 100],
          },
        },
        margin: { t: 24, l: 16, r: 16, b: 22 },
        autosize: true,
      }}
      style={{ width: '100%', height: '100%' }}
      useResizeHandler
      config={{ responsive: true, displayModeBar: false }}
    />
  );
}
