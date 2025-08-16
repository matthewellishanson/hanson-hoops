import React, { useEffect, useRef, useState } from 'react';
import PlayerRadarChart from './PlayerRadarChart';
import ShotMap from './ShotMap';
import '../PlayerCard.css';


export default function PlayerCard({ playerId, playerName, season, onReplace, style }) {
  const [flipped, setFlipped] = useState(false);
  const [backMounted, setBackMounted] = useState(false);
  const faceRef = useRef(null);

  // ⬇️ reset flip whenever the player changes
  useEffect(() => {
    setFlipped(false);
    setBackMounted(false);
    // nudge plotly after layout changes
    const t = setTimeout(() => window.dispatchEvent(new Event('resize')), 60);
    return () => clearTimeout(t);
  }, [playerId]);
  
  useEffect(() => {
    if (flipped) setBackMounted(true);
    const t = setTimeout(() => window.dispatchEvent(new Event('resize')), 80);
    return () => clearTimeout(t);
  }, [flipped]);

  useEffect(() => {
    if (!faceRef.current) return;
    const ro = new ResizeObserver(() => {
      window.dispatchEvent(new Event('resize'));
    });
    ro.observe(faceRef.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="pcard" style={style}>
      <div className={`pcard-flip ${flipped ? 'is-flipped' : ''}`}>
        <div className="pcard-face pcard-front" ref={faceRef} aria-hidden={flipped}>
          <div className="pcard-header">
            <h2 className="pcard-title">{playerName}</h2>
            <button className="pcard-link" onClick={onReplace}>Replace</button>
          </div>

          <div className="chart-container" aria-live="polite">
            <PlayerRadarChart playerId={playerId} season={season} playerName={playerName} />
          </div>

          <div className="pcard-footer">
            <button className="pcard-btn" onClick={() => setFlipped(true)}>
              See back →
            </button>
          </div>
        </div>

        <div className="pcard-face pcard-back" aria-hidden={!flipped}>
          <div className="pcard-header">
            <h2 className="pcard-title">{playerName} — Shot Map</h2>
            <button className="pcard-link" onClick={onReplace}>Replace</button>
          </div>

          <div className="chart-container" aria-live="polite">
            {backMounted && <ShotMap playerId={playerId} season={season} />}
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
