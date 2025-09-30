import React, { useEffect, useState } from 'react';
import * as Plotly from 'plotly.js-dist-min';
import Plot from 'react-plotly.js';
import { api } from '../lib/api';

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

export default function ShotMap({ playerId, season }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!playerId) { setData(null); return; }
    let active = true;
    (async () => {
      try {
        const res = await api.get('/player_shots', { params: { player_id: playerId, season } });
        if (active) setData(res.data);
      } catch (e) {
        console.error('Error fetching shots:', e);
        if (active) setData({ shots: [] });
      }
    })();
    return () => { active = false; };
  }, [playerId, season]);

  if (!playerId) return <div>Select a player to see a shot map.</div>;
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

  if (!data.shots || data.shots.length === 0) {
    return (
      <div className="text-muted" style={{padding: 12}}>
        No shot attempts recorded for this player in {season}.
      </div>
    );
  }

  const made = data.shots.filter(s => s.made);
  const missed = data.shots.filter(s => !s.made);

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

  return (
    <Plot
      data={[madeTrace, missTrace, arcTrace]}
      layout={{
        showlegend: true,
        legend: { orientation: 'h', x: 0.5, xanchor: 'center', y: -0.15 },
        xaxis: { range: [-250, 250], visible: false, zeroline: false, showgrid: false, constrain: 'domain' },
        yaxis: { range: [-50, 500], visible: false, zeroline: false, showgrid: false, scaleanchor: 'x', scaleratio: 1 },
        margin: { t: 24, l: 16, r: 16, b: 24 },
        shapes: courtShapesWithoutArc(),
        paper_bgcolor: 'white',
        plot_bgcolor: 'white',
        autosize: true,
      }}
      style={{ width: '100%', height: '100%' }}
      useResizeHandler
      config={{ responsive: true, displayModeBar: false }}
    />
  );
}
