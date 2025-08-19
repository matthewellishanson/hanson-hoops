import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import axios from 'axios';

// --- copied from your ShotMap.jsx: use the same court ---
function courtShapesWithoutArc() {
  const lineColor = '#0b3366';
  const lineW = 2;
  const rimR = 7.5, backboardY = -7.5, laneW = 160, laneH = 190;
  const ftLineY = 190, ftCircleR = 60;
  const corner3X = 220, arcR = 237.5;
  const corner3Y = Math.sqrt(arcR*arcR - corner3X*corner3X);

  return [
    { type: 'circle', xref: 'x', yref: 'y', x0: -rimR, y0: -rimR, x1: rimR, y1: rimR,
      line: { color: lineColor, width: lineW }, layer: 'above' },
    { type: 'line', xref: 'x', yref: 'y', x0: -30, y0: backboardY, x1: 30, y1: backboardY,
      line: { color: lineColor, width: lineW+1 }, layer: 'above' },
    { type: 'rect', xref: 'x', yref: 'y', x0: -laneW/2, y0: 0, x1: laneW/2, y1: laneH,
      line: { color: lineColor, width: lineW }, fillcolor: 'rgba(0,0,0,0)', layer: 'above' },
    { type: 'path', xref: 'x', yref: 'y',
      path: `M ${-ftCircleR} ${ftLineY} A ${ftCircleR} ${ftCircleR} 0 0 1 ${ftCircleR} ${ftLineY}`,
      line: { color: lineColor, width: lineW }, layer: 'above' },
    { type: 'line', xref: 'x', yref: 'y', x0: -corner3X, y0: 0, x1: -corner3X, y1: corner3Y,
      line: { color: lineColor, width: lineW }, layer: 'above' },
    { type: 'line', xref: 'x', yref: 'y', x0:  corner3X, y0: 0, x1:  corner3X, y1: corner3Y,
      line: { color: lineColor, width: lineW }, layer: 'above' },
    { type: 'rect', xref: 'x', yref: 'y', x0: -250, y0: 0, x1: 250, y1: 470,
      line: { color: lineColor, width: lineW }, fillcolor: 'rgba(0,0,0,0)', layer: 'above' },
  ];
}

function arcTrace() {
  const corner3X = 220, arcR = 237.5;
  const corner3Y = Math.sqrt(arcR*arcR - corner3X*corner3X);
  const thetaMax = Math.acos(corner3Y / arcR);
  const steps = 240;
  const theta = Array.from({ length: steps + 1 }, (_, i) =>
    -thetaMax + (2 * thetaMax * i) / steps
  );
  const arcX = theta.map(t => arcR * Math.sin(t));
  const arcY = theta.map(t => arcR * Math.cos(t));
  return {
    x: arcX,
    y: arcY,
    mode: 'lines',
    line: { width: 2, color: '#0b3366' },
    hoverinfo: 'skip',
    showlegend: false,
  };
}

export default function TeamShotMap({ teamId, season }) {
  const [data, setData] = useState(null);
  const [showFor, setShowFor] = useState(true);
  const [showAgainst, setShowAgainst] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await axios.get('http://localhost:8000/team_shots', {
          params: { team_id: teamId, season }
        });
        if (alive) setData(res.data);
      } catch (e) {
        console.error('Error fetching team shots:', e);
        if (alive) setData({ shots_for: [], shots_against: [] });
      }
    })();
    return () => { alive = false; };
  }, [teamId, season]);

  if (!data) return <div>Loading team shot map…</div>;

  const forMade = data.shots_for.filter(s => s.made);
  const forMiss = data.shots_for.filter(s => !s.made);
  const agMade  = data.shots_against.filter(s => s.made);
  const agMiss  = data.shots_against.filter(s => !s.made);

  const traces = [];

  if (showFor) {
    traces.push(
      {
        x: forMade.map(s => s.x), y: forMade.map(s => s.y),
        type: 'scattergl', mode: 'markers', name: 'For (Made)',
        marker: { size: 6, opacity: 0.8 }
      },
      {
        x: forMiss.map(s => s.x), y: forMiss.map(s => s.y),
        type: 'scattergl', mode: 'markers', name: 'For (Miss)',
        marker: { size: 6, opacity: 0.45 }
      }
    );
  }
  if (showAgainst) {
    traces.push(
      {
        x: agMade.map(s => s.x), y: agMade.map(s => s.y),
        type: 'scattergl', mode: 'markers', name: 'Allowed (Made)',
        marker: { size: 6, opacity: 0.8 }
      },
      {
        x: agMiss.map(s => s.x), y: agMiss.map(s => s.y),
        type: 'scattergl', mode: 'markers', name: 'Allowed (Miss)',
        marker: { size: 6, opacity: 0.45 }
      }
    );
  }

  // Add the arc as a trace so it stays perfectly curved
  traces.push(arcTrace());

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <label><input type="checkbox" checked={showFor} onChange={e => setShowFor(e.target.checked)} /> Show For</label>
        <label><input type="checkbox" checked={showAgainst} onChange={e => setShowAgainst(e.target.checked)} /> Show Allowed</label>
      </div>

      <Plot
        data={traces}
        layout={{
          showlegend: true,
          legend: { orientation: 'h', x: 0.5, xanchor: 'center', y: -0.15 },
          xaxis: { range: [-250, 250], visible: false, zeroline: false, showgrid: false, constrain: 'domain' },
          yaxis: { range: [-50, 500],  visible: false, zeroline: false, showgrid: false, scaleanchor: 'x', scaleratio: 1 },
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
    </div>
  );
}
