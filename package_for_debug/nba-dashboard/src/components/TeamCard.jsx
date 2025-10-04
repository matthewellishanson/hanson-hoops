import React, { useEffect, useRef, useState } from 'react';
import TeamRadarChart from './TeamRadarChart';
import TeamShotMap from './TeamShotMap';
import { api } from '../lib/api';
import '../PlayerCard.css';

export default function TeamCard({ teamId, teamName, season, onReplace, style }) {
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
  }, [teamId]);

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

  // Fetch team bio
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if (!teamId) return;
        const { data } = await api.get('/team_bio', {
          params: { team_id: teamId, season }
        });
        if (alive) setBio(data);
      } catch (e) {
        console.error('Error fetching team bio:', e);
        if (alive) setBio(null);
      }
    })();

    setFlipped(false);
    setBackMounted(false);
    const t = setTimeout(() => window.dispatchEvent(new Event('resize')), 60);
    return () => { alive = false; clearTimeout(t); };
  }, [teamId, season]);

  return (
    <div className="pcard" style={style}>
      <div className={`pcard-flip ${flipped ? 'is-flipped' : ''}`}>
        {/* FRONT */}
        <div className="pcard-face pcard-front" ref={faceRef}>
          <TeamHeaderBar bio={bio} fallbackName={teamName} onReplace={onReplace} season={season} />
          <div className="chart-container">
            <TeamRadarChart key={`${teamId}-${season}`} teamId={teamId} season={season} teamName={teamName} />
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
          <TeamHeaderBar bio={bio} fallbackName={teamName} onReplace={onReplace} season={season} />
          <div className="chart-container">
            {backMounted ? (
              <TeamShotMap teamId={teamId} season={season} />
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

function TeamHeaderBar({ bio, fallbackName, onReplace, season }) {
  const name = bio?.name || fallbackName;
  const logo = bio?.logo_url;
  const record = bio?.record;
  const standing = bio?.standing;
  const coach = bio?.coach;
  const arena = bio?.arena;
  const seasonLabel = season;

  return (
    <div className="pcard-header">
      <div className="pcard-header-left">
        {logo ? (
          <img className="pcard-headshot" src={logo} alt={name} />
        ) : (
          <div className="pcard-headshot placeholder" />
        )}
        <div className="pcard-titleblock">
          <div className="pcard-title">{name}</div>
          <div className="pcard-sub">
            {seasonLabel ? <span>{seasonLabel}</span> : null}
            {record ? <span> • {record}</span> : null}
            {standing ? <span> • {standing}</span> : null}
          </div>
        </div>
      </div>

      <div className="pcard-meta">
        {coach ? <span>Coach: {coach}</span> : null}
        {arena ? <span>Arena: {arena}</span> : null}
      </div>

      <button className="pcard-link" onClick={onReplace}>
        Replace
      </button>
    </div>
  );
}
