import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';
import axios from 'axios';

export default function ShotMap({ playerId, season }) {
  const [data, setData] = useState(null);

  useEffect(() => {
  if (!playerId) { setData(null); return; }      // ✅ guard
  let active = true;
  (async () => {
    try {
      const res = await axios.get('http://localhost:8000/player_shots', {
        params: { player_id: playerId, season }
      });
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

  return (
    <Plot
      data={[madeTrace, missTrace]}
      layout={{
        showlegend: true,
        legend: { orientation: 'h', x: 0.5, xanchor: 'center', y: -0.2 },
        xaxis: { visible: false, range: [-250, 250] },
        yaxis: { visible: false, range: [-50, 420] },
        margin: { t: 24, l: 16, r: 16, b: 22 },
        autosize: true
      }}
      style={{ width: '100%', height: '100%' }}
      useResizeHandler
      config={{ responsive: true, displayModeBar: false }}
    />
  );
}
