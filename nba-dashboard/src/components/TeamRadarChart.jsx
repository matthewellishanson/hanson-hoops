import React, { useEffect, useState } from 'react';
import * as Plotly from 'plotly.js-dist-min';
import Plot from 'react-plotly.js';
import axios from 'axios';

// Let react-plotly.js find Plotly on window (same pattern as your other charts)
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
        // Expected backend: /team_profile_stats returns normalized 0–100 values
        // plus raw_* fields (season averages) for tooltips.
        const { data } = await axios.get('http://localhost:8000/team_profile_stats', {
          params: { team_id: teamId, season }
        });
        if (alive) { setStats(data); setError(null); }
      } catch (e) {
        console.error('Error fetching team profile stats:', e);
        if (alive) { setStats(null); setError('Team data unavailable.'); }
      }
    })();
    return () => { alive = false; };
  }, [teamId, season]);

  if (!teamId) return <div>Select a team to see a chart.</div>;
  if (error) return <div>{error}</div>;
  if (!stats) return <div>Loading team chart…</div>;

  // ------- TEAM view (normalized 0–100) -------
  const teamTheta = ['Points', 'Rebounds', 'Assists', 'Blocks', 'Steals', 'FG%', '3P%'];
  const teamR = [
    stats.points, stats.rebounds, stats.assists,
    stats.blocks, stats.steals, stats.fg_pct, stats.fg3_pct
  ];
  const teamHover = [
    `Points: ${stats.raw_points} PPG`,
    `Rebounds: ${stats.raw_rebounds} RPG`,
    `Assists: ${stats.raw_assists} APG`,
    `Blocks: ${stats.raw_blocks} BPG`,
    `Steals: ${stats.raw_steals} SPG`,
    `FG%: ${stats.raw_fg_pct}%`,
    `3P%: ${stats.raw_fg3_pct}%`,
  ];

  // ------- OPPONENT view (normalized 0–100) -------
  // Expect: opp_points, opp_fg_pct, opp_fg3_pct + raw_opp_* counterparts
  const oppTheta = ['Opp Pts', 'Opp FG%', 'Opp 3P%'];
  const oppR = [stats.opp_points, stats.opp_fg_pct, stats.opp_fg3_pct];
  const oppHover = [
    `Opp Points: ${stats.raw_opp_points} PPG`,
    `Opp FG%: ${stats.raw_opp_fg_pct}%`,
    `Opp 3P%: ${stats.raw_opp_fg3_pct}%`,
  ];

  // Basic guards against undefined/NaN
  const isFiniteArray = (arr) => arr.every(v => Number.isFinite(v));
  const validTeam = isFiniteArray(teamR);
  const validOpp = isFiniteArray(oppR);

  const chartData = mode === 'team'
    ? [{
        type: 'scatterpolar',
        r: teamR,
        theta: teamTheta,
        fill: 'toself',
        text: teamHover,
        hoverinfo: 'text',
        name: `${teamName} (Team)`
      }]
    : [{
        type: 'scatterpolar',
        r: oppR,
        theta: oppTheta,
        fill: 'toself',
        text: oppHover,
        hoverinfo: 'text',
        name: `${teamName} (Opponent)`
      }];

  const hasData = mode === 'team' ? validTeam : validOpp;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Simple toggle */}
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

      {hasData ? (
        <Plot
          data={chartData}
          layout={{
            title: `${teamName} Profile`,
            polar: {
              radialaxis: {
                visible: true,
                range: [0, 100],
                tickvals: [0, 20, 40, 60, 80, 100],
              }
            },
            margin: { t: 24, l: 16, r: 16, b: 22 },
            autosize: true
          }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler
          config={{ responsive: true, displayModeBar: false }}
        />
      ) : (
        <div>Data unavailable for this selection.</div>
      )}
    </div>
  );
}
