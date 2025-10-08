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
          // ask for percentile scaling explicitly (safe even if backend defaults)
          params: { player_id: playerId, season, scale: 'percentile' },
        });
        console.log('[Radar] payload', data);
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

  // helpers
  const isFiniteNumber = (v) => typeof v === 'number' && Number.isFinite(v);
  const clamp01 = (v) => Math.max(0, Math.min(100, v ?? 0));

  // The exact keys you plot (order matches theta)
  const metricKeys = [
    'points', 'rebounds', 'assists', 'blocks', 'steals',
    'fg_pct', 'fg3_pct', 'ft_rate', 'ft_pct', 'turnovers',
  ];

  // Availability: at least one numeric metric (0 is valid)
  const hasAnyMetric = !!stats && metricKeys.some((k) => isFiniteNumber(stats[k]));
  if (!hasAnyMetric) return <div>Data unavailable for this selection.</div>;

  // r values (visual 0–100); sanitize NaN/undefined → 0 and clamp
  const theta = [
    'Points', 'Rebounds', 'Assists', 'Blocks', 'Steals',
    'FG%', '3P%', 'FT Rate', 'FT%', 'Turnovers (↓ better)',
  ];
  const r = metricKeys.map((k) => clamp01(isFiniteNumber(stats[k]) ? stats[k] : 0));

  // Tooltips: show real numbers from backend (raw fields)
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

  // Optional: if you want to hide a completely flat shape (all zeros)
  const allZero = r.every((v) => v === 0);
  if (allZero) return <div>Data unavailable for this selection.</div>;

  return (
    <Plot
      data={[{
        type: 'scatterpolar',
        r,
        theta,
        fill: 'toself',
        text: hoverText,
        hoverinfo: 'text',
        name: playerName,
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
