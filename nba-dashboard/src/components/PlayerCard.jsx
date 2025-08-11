import React, { useEffect, useState } from 'react';
import { Card, Button } from 'react-bootstrap';
import PlayerRadarChart from './PlayerRadarChart';
import ShotMap from './ShotMap'; // new component
import '../PlayerCard.css'; // Adjust the path as necessary

export default function PlayerCard({ playerId, playerName, season, onReplace }) {
  const [flipped, setFlipped] = useState(false);
  const [backMounted, setBackMounted] = useState(false);

  useEffect(() => {
    if (flipped) setBackMounted(true);
    // give Plotly a tick to recalc after transform
    const t = setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 60);
    return () => clearTimeout(t);
  }, [flipped]);

  return (
    <div className="pcard">
      <div className={`pcard-flip ${flipped ? 'is-flipped' : ''}`}>
        {/* FRONT */}
        <div className="pcard-face pcard-front">
          <div className="pcard-header">
            <h2 className="pcard-title">{playerName}</h2>
            <button className="pcard-link" onClick={onReplace}>Replace</button>
          </div>

          <div className="chart-container">
            <PlayerRadarChart
              playerId={playerId}
              season={season}
              playerName={playerName}
            />
          </div>

          <div className="pcard-footer">
            <button className="pcard-btn" onClick={() => setFlipped(true)}>
              See back →
            </button>
          </div>
        </div>

        {/* BACK */}
        <div className="pcard-face pcard-back">
          <div className="pcard-header">
            <h2 className="pcard-title">{playerName} — Shot Map</h2>
            <button className="pcard-link" onClick={onReplace}>Replace</button>
          </div>

          <div className="chart-container">
            <ShotMap
              playerId={playerId}
              season={season}
            />
          </div>

          <div className="pcard-footer">
            <button className="pcard-btn secondary" onClick={() => setFlipped(false)}>
              ← See front
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

