import React, { useEffect, useRef, useState } from 'react';
import TeamRadarChart from './TeamRadarChart';
import TeamShotMap from './TeamShotMap';
// Reuse PlayerCard styles for consistent look (or make a TeamCard.css)
import '../PlayerCard.css';

export default function TeamCard({ teamId, teamName, season, onReplace, style }) {
  const [flipped, setFlipped] = useState(false);
  const [backMounted, setBackMounted] = useState(false);
  const faceRef = useRef(null);
  const [bio, setBio] = useState(null);

  // era check (shot locations available from 1996–97 onward)
  const startYear = Number((season || '').split('-')[0]);
  const eraHasShots = startYear >= 1996;

  // Reset flip whenever the team changes
  useEffect(() => {
    setFlipped(false);
    setBackMounted(false);
    const t = setTimeout(() => window.dispatchEvent(new Event('resize')), 60);
    return () => clearTimeout(t);
  }, [teamId]);

  // When flipped, mount the back once and nudge Plotly
  useEffect(() => {
    if (flipped) setBackMounted(true);
    const t = setTimeout(() => window.dispatchEvent(new Event('resize')), 80);
    return () => clearTimeout(t);
  }, [flipped]);

  // Resize observer (same pattern as PlayerCard)
  useEffect(() => {
    if (!faceRef.current) return;
    const ro = new ResizeObserver(() => {
      window.dispatchEvent(new Event('resize'));
    });
    ro.observe(faceRef.current);
    return () => ro.disconnect();
  }, []);

  // Fetch team bio when teamId or season changes (age/record/standing can be season-relative)
  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        if (!teamId) return;
        const res = await fetch(
          `http://localhost:8000/team_bio?team_id=${teamId}&season=${encodeURIComponent(season)}`
        );
        if (!res.ok) throw new Error('team bio fetch failed');
        const data = await res.json();
        if (alive) setBio(data);
      } catch (e) {
        console.error('Error fetching team bio:', e);
        if (alive) setBio(null);
      }
    }
    load();

    // reset flip on team change
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
            {/* Force remount when team or season changes */}
            <TeamRadarChart
              key={`${teamId}-${season}`}
              teamId={teamId}
              season={season}
              teamName={teamName}
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

/** Compact team header (mirrors Player header) */
function TeamHeaderBar({ bio, fallbackName, onReplace, season }) {
  const name = bio?.name || fallbackName;
  const logo = bio?.logo_url;                 // e.g., https://.../team_logos/1610612755.svg
  const record = bio?.record;                 // e.g., "54–28"
  const standing = bio?.standing;             // e.g., "2nd in East" or "5th Overall"
  const coach = bio?.coach;                   // optional
  const arena = bio?.arena;                   // optional
  const seasonLabel = season;                 // show current card season

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
