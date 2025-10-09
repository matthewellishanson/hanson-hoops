import React, { useEffect, useRef, useState } from 'react';
import PlayerRadarChart from './PlayerRadarChart';
import ShotMap from './ShotMap';
import { api } from '../lib/api';
import '../PlayerCard.css';
import '../global.css';

export default function PlayerCard({ playerId, playerName, season, onReplace, style }) {
  const [flipped, setFlipped] = useState(false);
  const [backMounted, setBackMounted] = useState(false);
  const faceRef = useRef(null);
  const [bio, setBio] = useState(null);
  const startYear = Number((season || '').split('-')[0]);
  const eraHasShots = startYear >= 1996;

  useEffect(() => {
    setFlipped(false);
    setBackMounted(false);
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

  // Fetch bio when playerId changes
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if (!playerId) return;
        const { data } = await api.get('/player_bio', {
          params: { player_id: playerId, season }
        });
        if (alive) setBio(data);
      } catch (e) {
        console.error('Error fetching bio:', e);
        if (alive) setBio(null);
      }
    })();

    setFlipped(false);
    setBackMounted(false);
    const t = setTimeout(() => window.dispatchEvent(new Event('resize')), 60);
    return () => { alive = false; clearTimeout(t); };
  }, [playerId, season]);

  return (
    <div className="pcard" style={style}>
      <div className={`pcard-flip ${flipped ? 'is-flipped' : ''}`}>
        {/* FRONT */}
        <div className="pcard-face pcard-front">
          <HeaderBar bio={bio} fallbackName={playerName} onReplace={onReplace} />
          <div className="chart-container">
            <PlayerRadarChart
              key={`${playerId}-${season}`}
              playerId={playerId}
              season={season}
              playerName={playerName}
            />
          </div>
          <div className="pcard-footer">
            <button
              className="pcard-btn"
              disabled={!eraHasShots}
              title={!eraHasShots ? 'No shot map data before 1996–97' : undefined}
              onClick={() => { if (eraHasShots) { setBackMounted(true); setFlipped(true); } }}
            >
              See back →
            </button>
          </div>
        </div>

        {/* BACK */}
        <div className="pcard-face pcard-back">
          <HeaderBar bio={bio} fallbackName={playerName} onReplace={onReplace} />
          <div className="chart-container">
            {backMounted ? (
              <ShotMap playerId={playerId} season={season} />
            ) : (
              <div>Loading…</div>
            )}
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

function HeaderBar({ bio, fallbackName, onReplace }) {
  const name = bio?.name || fallbackName;
  const team = bio?.team;
  const pos = bio?.position;
  const age = bio?.age;
  const ht = bio?.height;
  const htcm = bio?.height_cm;
  const wt = bio?.weight_lbs;
  const jersey = bio?.jersey;
  const headshot = bio?.headshot_url;

  return (
    <div className="pcard-header">
      <div className="pcard-header-left">
        {headshot ? (
          <img className="pcard-headshot" src={headshot} alt={name} />
        ) : (
          <div className="pcard-headshot placeholder" />
        )}
        <div className="pcard-titleblock">
          <div className="pcard-title">{name}</div>
          <div className="pcard-sub">
            {team ? <span>{team}</span> : null}
            {pos ? <span> • {pos}</span> : null}
            {jersey ? <span> • #{jersey}</span> : null}
          </div>
        </div>
      </div>

      <div className="pcard-meta">
        {age != null && <span>Age: {age}</span>}
        {ht && <span>Height: {ht}{htcm ? ` (${htcm} cm)` : ''}</span>}
        {wt != null && <span>Weight: {wt} lbs</span>}
      </div>

      <button className="pcard-link" onClick={onReplace}>
        Replace
      </button>
    </div>
  );
}
