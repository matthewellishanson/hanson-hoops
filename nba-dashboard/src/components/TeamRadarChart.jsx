import React, { useEffect, useState } from 'react';
import * as Plotly from 'plotly.js-dist-min';
import Plot from 'react-plotly.js';
import { apiErrorMessage, sharedGet } from '../lib/api';

const ACCENT = '#7c3aed';

// Let react-plotly.js find Plotly on window
if (typeof window !== 'undefined' && !window.Plotly) {
  window.Plotly = Plotly;
}

export default function TeamRadarChart({ teamId, season, teamName = 'Team' }) {
  const [stats, setStats] = useState(null);
  const [mode, setMode] = useState('team'); // 'team' | 'opponent'
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if (!teamId) return;
        const { data } = await sharedGet('/team_profile_stats', {
          team_id: teamId, season, scale: 'percentile', opp_scale: 'percentile',
        });
        if (!alive) return;
        setStats(data);
        setError(null);
      } catch (e) {
        console.error('Error fetching team profile stats:', e);
        if (alive) { setStats(null); setError(apiErrorMessage(e, 'Team data unavailable.')); }
      }
    })();
    return () => { alive = false; };
  }, [teamId, season]);

  if (!teamId) return <div>Select a team to see a chart.</div>;
  if (error) return <div>{error}</div>;
  if (!stats) return <div>Loading team chart…</div>;

  const isFiniteNumber = (v) => typeof v === 'number' && Number.isFinite(v);
  const clamp01 = (v) => Math.max(0, Math.min(100, v ?? 0));
  const sanitize = (arr) => arr.map((v) => clamp01(isFiniteNumber(v) ? v : 0));
  const anyFinite = (arr) => arr.some(isFiniteNumber);
  const allZero = (arr) => arr.every((v) => v === 0);

  // TEAM mode (0–100)
  const teamTheta = ['Points', 'Rebounds', 'Assists', 'Blocks', 'Steals', 'FG%', '3P%', 'Turnovers (↓ better)'];
  const teamR_raw = [
    stats?.points, stats?.rebounds, stats?.assists,
    stats?.blocks, stats?.steals, stats?.fg_pct, stats?.fg3_pct, stats?.turnovers,
  ];
  const teamR = sanitize(teamR_raw);
  const teamHover = [
    `Points: ${stats?.raw_points ?? '—'} PPG`,
    `Rebounds: ${stats?.raw_rebounds ?? '—'} RPG`,
    `Assists: ${stats?.raw_assists ?? '—'} APG`,
    `Blocks: ${stats?.raw_blocks ?? '—'} BPG`,
    `Steals: ${stats?.raw_steals ?? '—'} SPG`,
    `FG%: ${stats?.raw_fg_pct ?? '—'}%`,
    `3P%: ${stats?.raw_fg3_pct ?? '—'}%`,
    `Turnovers: ${stats?.raw_tov ?? '—'} TOPG`,
  ];

  // OPPONENT mode (0–100)
  const oppTheta = ['Opp Pts', 'Opp FG%', 'Opp 3P%', 'Opp AST', 'Opp REB', 'Opp FTM', 'Opp FT%'];
  const oppR_raw = [
    stats?.opp_points, stats?.opp_fg_pct, stats?.opp_fg3_pct,
    stats?.opp_ast, stats?.opp_reb, stats?.opp_ftm, stats?.opp_ft_pct,
  ];
  const oppR = sanitize(oppR_raw);
  const oppHover = [
    `Opp Points: ${stats?.raw_opp_points ?? '—'} PPG`,
    `Opp FG%: ${stats?.raw_opp_fg_pct ?? '—'}%`,
    `Opp 3P%: ${stats?.raw_opp_fg3_pct ?? '—'}%`,
    `Opp Assists: ${stats?.raw_opp_ast ?? '—'} APG`,
    `Opp Rebounds: ${stats?.raw_opp_reb ?? '—'} RPG`,
    `Opp Free Throws: ${stats?.raw_opp_ftm ?? '—'} FTM/G`,
    `Opp FT%: ${stats?.raw_opp_ft_pct ?? '—'}%`,
  ];

  // Choose mode arrays
  const rBase = mode === 'team' ? teamR : oppR;
  const thetaBase = mode === 'team' ? teamTheta : oppTheta;
  const hoverBase = mode === 'team' ? teamHover : oppHover;
  const hasData = mode === 'team' ? anyFinite(teamR_raw) : anyFinite(oppR_raw);

  if (!hasData || allZero(rBase)) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div className="btn-group" role="group" aria-label="mode">
          <button
            type="button"
            className={`btn btn-sm ${mode === 'team' ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => setMode('team')}
          >
            Team
          </button>
          <button
            type="button"
            className={`btn btn-sm ${mode === 'opponent' ? 'btn-primary' : 'btn-outline-primary'}`}
            onClick={() => setMode('opponent')}
          >
            Opponent
          </button>
        </div>
        <div>Data unavailable for this selection.</div>
      </div>
    );
  }

  // 🔒 Close the loop
  const rClosed = [...rBase, rBase[0]];
  const thetaClosed = [...thetaBase, thetaBase[0]];
  const hoverClosed = [...hoverBase, hoverBase[0]];

  const chartData = [{
    type: 'scatterpolar',
    r: rClosed,
    theta: thetaClosed,
    fill: 'toself',
    text: hoverClosed,
    hoverinfo: 'text',
    name: mode === 'team' ? `${teamName} (Team)` : `${teamName} (Opponent)`,
    line: { color: ACCENT },
    marker: { color: ACCENT },
    fillcolor: 'rgba(124,58,237,0.25)',
  }];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div className="btn-group" role="group" aria-label="mode">
        <button
          type="button"
          className={`btn btn-sm ${mode === 'team' ? 'btn-primary' : 'btn-outline-primary'}`}
          onClick={() => setMode('team')}
        >
          Team
        </button>
        <button
          type="button"
          className={`btn btn-sm ${mode === 'opponent' ? 'btn-primary' : 'btn-outline-primary'}`}
          onClick={() => setMode('opponent')}
        >
          Opponent
        </button>
      </div>

      <Plot
        data={chartData}
        layout={{
          title: `${teamName} Profile`,
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
    </div>
  );
}
