import React, { useEffect, useState } from 'react';
import * as Plotly from 'plotly.js-dist-min';
import Plot from 'react-plotly.js';
import { apiErrorMessage, sharedGet } from '../lib/api';

// Let react-plotly.js find Plotly on window
if (typeof window !== 'undefined' && !window.Plotly) {
  window.Plotly = Plotly;
}

// ---- Court constants ----
const RIM_R = 7.5;
const BACKBOARD_Y = -7.5;
const LANE_W = 160;
const LANE_H = 190;
const FT_LINE_Y = 190;
const FT_CIRCLE_R = 60;
const CORNER3_X = 220;
const ARC_R = 237.5;
const CORNER3_Y = Math.sqrt(ARC_R * ARC_R - CORNER3_X * CORNER3_X);
const LINE_COLOR = '#0b3366';
const LINE_W = 2;

function courtShapesWithoutArc() {
  return [
    { type: 'circle', xref: 'x', yref: 'y', x0: -RIM_R, y0: -RIM_R, x1: RIM_R, y1: RIM_R, line: { color: LINE_COLOR, width: LINE_W }, layer: 'above' },
    { type: 'line', xref: 'x', yref: 'y', x0: -30, y0: BACKBOARD_Y, x1: 30, y1: BACKBOARD_Y, line: { color: LINE_COLOR, width: LINE_W + 1 }, layer: 'above' },
    { type: 'rect', xref: 'x', yref: 'y', x0: -LANE_W / 2, y0: 0, x1: LANE_W / 2, y1: LANE_H, line: { color: LINE_COLOR, width: LINE_W }, fillcolor: 'rgba(0,0,0,0)', layer: 'above' },
    { type: 'path', xref: 'x', yref: 'y', path: `M ${-FT_CIRCLE_R} ${FT_LINE_Y} A ${FT_CIRCLE_R} ${FT_CIRCLE_R} 0 0 1 ${FT_CIRCLE_R} ${FT_LINE_Y}`, line: { color: LINE_COLOR, width: LINE_W }, layer: 'above' },
    { type: 'line', xref: 'x', yref: 'y', x0: -CORNER3_X, y0: 0, x1: -CORNER3_X, y1: CORNER3_Y, line: { color: LINE_COLOR, width: LINE_W }, layer: 'above' },
    { type: 'line', xref: 'x', yref: 'y', x0:  CORNER3_X, y0: 0, x1:  CORNER3_X, y1: CORNER3_Y, line: { color: LINE_COLOR, width: LINE_W }, layer: 'above' },
    { type: 'rect', xref: 'x', yref: 'y', x0: -250, y0: 0, x1: 250, y1: 470, line: { color: LINE_COLOR, width: LINE_W }, fillcolor: 'rgba(0,0,0,0)', layer: 'above' },
  ];
}

function buildArcTrace() {
  const thetaMax = Math.acos(CORNER3_Y / ARC_R);
  const steps = 240;
  const theta = Array.from({ length: steps + 1 }, (_, i) => -thetaMax + (2 * thetaMax * i) / steps);
  const arcX = theta.map(t => ARC_R * Math.sin(t));
  const arcY = theta.map(t => ARC_R * Math.cos(t));
  return { x: arcX, y: arcY, mode: 'lines', line: { width: LINE_W, color: LINE_COLOR }, hoverinfo: 'skip', showlegend: false };
}

// --- helpers to make the pill summary like the team one ---
function summarizeShots(shots) {
  if (!shots || shots.length === 0) {
    return { fg_pct: 0, fgm: 0, fga: 0, fg3_pct: 0, fg3m: 0, fg3a: 0 };
  }
  const fga = shots.length;
  const fgm = shots.reduce((acc, s) => acc + (s.made ? 1 : 0), 0);
  const fg_pct = fga ? (fgm / fga) * 100.0 : 0;

  // 3PT detection: prefer SHOT_TYPE prefix, fall back to distance >= 23 ft
  const isThree = (s) =>
    (typeof s.shot_type === 'string' && s.shot_type.toUpperCase().startsWith('3PT')) ||
    (typeof s.shot_distance === 'number' && s.shot_distance >= 23);

  const threes = shots.filter(isThree);
  const fg3a = threes.length;
  const fg3m = threes.reduce((acc, s) => acc + (s.made ? 1 : 0), 0);
  const fg3_pct = fg3a ? (fg3m / fg3a) * 100.0 : 0;

  return {
    fg_pct: Number.isFinite(fg_pct) ? fg_pct : 0,
    fgm, fga,
    fg3_pct: Number.isFinite(fg3_pct) ? fg3_pct : 0,
    fg3m, fg3a,
  };
}

const Pill = ({ title, s }) => (
  <div className="map-pill for">
    <div style={{ fontSize: 12, opacity: 0.9 }}>{title}</div>
    <div style={{ fontSize: 14 }}>
      <strong>FG</strong> {s.fg_pct?.toFixed?.(1) ?? s.fg_pct}% ({s.fgm}-{s.fga})
    </div>
    <div style={{ fontSize: 14 }}>
      <strong>3PT</strong> {s.fg3_pct?.toFixed?.(1) ?? s.fg3_pct}% ({s.fg3m}-{s.fg3a})
    </div>
  </div>
);

export default function ShotMap({ playerId, season }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!playerId) { setData(null); setError(''); return; }
    let active = true;
    (async () => {
      try {
        const res = await sharedGet('/player_shots', { params: { player_id: playerId, season } });
        if (active) { setData(res.data); setError(''); }
        // ensure Plotly resizes under grid layouts
        setTimeout(() => window.dispatchEvent(new Event('resize')), 50);
      } catch (e) {
        console.error('Error fetching shots:', e);
        if (active) { setData(null); setError(apiErrorMessage(e, 'Shot chart unavailable.')); }
        setTimeout(() => window.dispatchEvent(new Event('resize')), 50);
      }
    })();
    return () => { active = false; };
  }, [playerId, season]);

  if (!playerId) return <div>Select a player to see a shot map.</div>;
  if (error) return <div className="text-muted" style={{padding: 12}}>{error}</div>;
  if (!data) return <div>Loading shot map…</div>;

  const startYear = Number((season || '').split('-')[0]);
  const eraHasShots = startYear >= 1996;
  if (!eraHasShots) {
    return (
      <div className="text-muted" style={{padding: 12}}>
        No shot-location data is available league-wide before the 1996–97 season.
      </div>
    );
  }

  const shots = data.shots || [];
  if (shots.length === 0) {
    return (
      <div className="text-muted" style={{padding: 12}}>
        No shot attempts recorded for this player in {season}.
      </div>
    );
  }

  const made = shots.filter(s => s.made);
  const missed = shots.filter(s => !s.made);

  const madeTrace = {
    x: made.map(s => s.x),
    y: made.map(s => s.y),
    mode: 'markers',
    type: 'scattergl',
    name: 'Made',
    marker: { size: 6, opacity: 0.75 },
    hoverinfo: 'text',
    text: made.map(s => `Made • ${s.shot_zone ?? ''} • ${s.shot_distance ?? ''} ft`)
  };
  const missTrace = {
    x: missed.map(s => s.x),
    y: missed.map(s => s.y),
    mode: 'markers',
    type: 'scattergl',
    name: 'Missed',
    marker: { size: 6, opacity: 0.45 },
    hoverinfo: 'text',
    text: missed.map(s => `Miss • ${s.shot_zone ?? ''} • ${s.shot_distance ?? ''} ft`)
  };

  const arcTrace = buildArcTrace();
  const summary = summarizeShots(shots);

  return (
    <div className="map-wrap" style={{ height: '100%' }}>
      {/* teal pill, same style as team map's "Shots For" */}
      <Pill title="Shots" s={summary} />
      <Plot
        data={[madeTrace, missTrace, arcTrace]}
        layout={{
          showlegend: false, // keep it clean like team maps
          xaxis: { range: [-250, 250], visible: false, zeroline: false, showgrid: false, constrain: 'domain' },
          yaxis: { range: [-50, 500], visible: false, zeroline: false, showgrid: false, scaleanchor: 'x', scaleratio: 1 },
          margin: { t: 4, l: 4, r: 4, b: 4 },
          shapes: courtShapesWithoutArc(),
          paper_bgcolor: 'white',
          plot_bgcolor: 'white',
          autosize: true,
        }}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler
        config={{ responsive: true, displayModeBar: false }}
      />
    </div>
  );
}
