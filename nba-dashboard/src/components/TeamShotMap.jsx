import React, { useEffect, useState } from 'react';
import * as Plotly from 'plotly.js-dist-min';
import Plot from 'react-plotly.js';
import axios from 'axios';

if (typeof window !== 'undefined' && !window.Plotly) window.Plotly = Plotly;

// ---- shared court ----
function courtShapesWithoutArc() {
  const lineColor = '#0b3366';
  const lineW = 2;
  const rimR = 7.5, backboardY = -7.5, laneW = 160, laneH = 190;
  const ftLineY = 190, ftCircleR = 60;
  const corner3X = 220, arcR = 237.5;
  const corner3Y = Math.sqrt(arcR*arcR - corner3X*corner3X);
  return [
    { type: 'circle', xref: 'x', yref: 'y', x0: -rimR, y0: -rimR, x1: rimR, y1: rimR, line: { color: lineColor, width: lineW }, layer: 'above' },
    { type: 'line', xref: 'x', yref: 'y', x0: -30, y0: backboardY, x1: 30, y1: backboardY, line: { color: lineColor, width: lineW+1 }, layer: 'above' },
    { type: 'rect', xref: 'x', yref: 'y', x0: -laneW/2, y0: 0, x1: laneW/2, y1: laneH, line: { color: lineColor, width: lineW }, fillcolor: 'rgba(0,0,0,0)', layer: 'above' },
    { type: 'path', xref: 'x', yref: 'y', path: `M ${-ftCircleR} ${ftLineY} A ${ftCircleR} ${ftCircleR} 0 0 1 ${ftCircleR} ${ftLineY}`, line: { color: lineColor, width: lineW }, layer: 'above' },
    { type: 'line', xref: 'x', yref: 'y', x0: -corner3X, y0: 0, x1: -corner3X, y1: corner3Y, line: { color: lineColor, width: lineW }, layer: 'above' },
    { type: 'line', xref: 'x', yref: 'y', x0:  corner3X, y0: 0, x1:  corner3X, y1: corner3Y, line: { color: lineColor, width: lineW }, layer: 'above' },
    { type: 'rect', xref: 'x', yref: 'y', x0: -250, y0: 0, x1: 250, y1: 470, line: { color: lineColor, width: lineW }, fillcolor: 'rgba(0,0,0,0)', layer: 'above' },
  ];
}

function arcTrace() {
  const corner3X = 220, arcR = 237.5;
  const corner3Y = Math.sqrt(arcR*arcR - corner3X*corner3X);
  const thetaMax = Math.acos(corner3Y / arcR);
  const steps = 240;
  const theta = Array.from({ length: steps + 1 }, (_, i) => -thetaMax + (2 * thetaMax * i) / steps);
  const arcX = theta.map(t => arcR * Math.sin(t));
  const arcY = theta.map(t => arcR * Math.cos(t));
  return { x: arcX, y: arcY, mode: 'lines', line: { width: 2, color: '#0b3366' }, hoverinfo: 'skip', showlegend: false };
}

export default function TeamShotMap({ teamId, season }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await axios.get('http://localhost:8000/team_shots', { params: { team_id: teamId, season } });
        if (alive) setData(res.data);
      } catch (e) {
        console.error('Error fetching team shots:', e);
        if (alive) setData({
          shots_for: [], shots_against: [],
          summary_for: { fg_pct: 0, fgm: 0, fga: 0, fg3_pct: 0, fg3m: 0, fg3a: 0 },
          summary_against: { fg_pct: 0, fgm: 0, fga: 0, fg3_pct: 0, fg3m: 0, fg3a: 0 },
        });
      }
    })();
    return () => { alive = false; };
  }, [teamId, season]);

  if (!data) return <div>Loading team shot maps…</div>;

  const forMade = data.shots_for.filter(s => s.made);
  const forMiss = data.shots_for.filter(s => !s.made);
  const agMade  = data.shots_against.filter(s => s.made);
  const agMiss  = data.shots_against.filter(s => !s.made);

  // traces for each chart
  const makeTrace = (made, miss, nameMade, nameMiss) => ([
    { x: made.map(s => s.x), y: made.map(s => s.y), type: 'scattergl', mode: 'markers', name: nameMade,  marker: { size: 6, opacity: 0.8 } },
    { x: miss.map(s => s.x), y: miss.map(s => s.y), type: 'scattergl', mode: 'markers', name: nameMiss,  marker: { size: 6, opacity: 0.45 } },
    arcTrace(),
  ]);

  const baseLayout = {
    showlegend: false,
    xaxis: { range: [-250, 250], visible: false, zeroline: false, showgrid: false, constrain: 'domain' },
    yaxis: { range: [-50, 500],  visible: false, zeroline: false, showgrid: false, scaleanchor: 'x', scaleratio: 1 },
    margin: { t: 8, l: 8, r: 8, b: 8 },
    shapes: courtShapesWithoutArc(),
    paper_bgcolor: 'white',
    plot_bgcolor: 'white',
    autosize: true,
  };

  const pill = (cls, title, s) => (
    <div className={`map-pill ${cls}`}>
      <div style={{ fontSize: 12, opacity: 0.9 }}>{title}</div>
      <div style={{ fontSize: 14 }}>
        <strong>FG</strong> {s.fg_pct?.toFixed?.(1) ?? s.fg_pct}% ({s.fgm}-{s.fga})
      </div>
      <div style={{ fontSize: 14 }}>
        <strong>3PT</strong> {s.fg3_pct?.toFixed?.(1) ?? s.fg3_pct}% ({s.fg3m}-{s.fg3a})
      </div>
    </div>
  );

  return (
    <div className="shotmaps-grid">
      {/* FOR */}
      <div className="map-wrap">
        {pill('for', 'Shots For', data.summary_for || {fg_pct:0,fgm:0,fga:0,fg3_pct:0,fg3m:0,fg3a:0})}
        <Plot
          data={makeTrace(forMade, forMiss, 'Made', 'Miss')}
          layout={{ ...baseLayout }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler
          config={{ responsive: true, displayModeBar: false }}
        />
      </div>

      {/* ALLOWED */}
      <div className="map-wrap">
        {pill('against', 'Shots Allowed', data.summary_against || {fg_pct:0,fgm:0,fga:0,fg3_pct:0,fg3m:0,fg3a:0})}
        <Plot
          data={makeTrace(agMade, agMiss, 'Made', 'Miss')}
          layout={{ ...baseLayout }}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler
          config={{ responsive: true, displayModeBar: false }}
        />
      </div>
    </div>
  );
}
