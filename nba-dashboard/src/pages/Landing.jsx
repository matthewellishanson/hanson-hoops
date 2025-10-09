import React from 'react';
import { Link } from 'react-router-dom';

// Simple inline GitHub SVG to avoid extra deps
const GitHubIcon = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
    <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 0 0 5.47 7.59c.4.07.55-.17.55-.38
      0-.19-.01-.82-.01-1.49C3.73 14.91 3.27 13.4 3.27 13.4c-.36-.93-.88-1.18-.88-1.18
      -.72-.49.05-.48.05-.48.8.06 1.22.83 1.22.83.71 1.22 1.87.87 2.33.66.07-.52.28-.87.51-1.07
      -2.66-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.12-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23
      .96-.27 1.98-.4 3-.41 1.02.01 2.04.14 3 .41 2.29-1.55 3.3-1.23 3.3-1.23.66 1.65.24 2.87.12 3.17
      .77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.49 5.93.29.25.54.73.54 1.48
      0 1.07-.01 1.93-.01 2.19 0 .21.15.46.55.38A8.001 8.001 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
  </svg>
);

export default function Landing() {
  const handleShare = async () => {
    const url = window.location.href;
    const title = "Hanson Hoops: NBA Comparisons Tool";
    const text = "Compare up to 4 players or teams across seasons — stats and shot maps.";

    if (navigator.share) {
      try {
        await navigator.share({ title, text, url });
      } catch { /* user cancelled */ }
    } else {
      // Fallback: copy link
      try {
        await navigator.clipboard.writeText(url);
        alert("Link copied to clipboard!");
      } catch {
        window.prompt("Copy this URL:", url);
      }
    }
  };

  return (
    <div className="hero-container">
      {/* top-right actions */}
      <div className="hero-actions">
        <a
          href="https://github.com/matthewellishanson/hanson-hoops"
          target="_blank" rel="noreferrer"
          className="hero-icon-btn" aria-label="GitHub repository"
          title="GitHub"
        >
          <GitHubIcon />
        </a>
        <button className="hero-icon-btn" onClick={handleShare} aria-label="Share" title="Share">
          {/* simple share icon */}
          <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7a3.27 3.27 0 0 0 0-1.39l7.02-4.11A2.99 2.99 0 1 0 14 5
              c0 .2.02.39.07.57L7.05 9.69a3 3 0 1 0 0 4.62l7.02 4.11c-.05.18-.07.37-.07.57a3 3 0 1 0 3-3z"/>
          </svg>
        </button>
      </div>

      {/* overlay */}
      <div className="hero-overlay" />

      {/* content */}
      <div className="hero-content">
        <h1 className="hero-title">Hanson Hoops: NBA Comparisons Tool</h1>
        <p className="hero-sub">
          Pick up to 4 players or teams, any four players or teams, from any season,
          to see how basic statistics, advanced stats and shot distributions stack up to the other selected players or teams.
        </p>

        <div className="hero-cta">
          <Link to="/players" className="cta-card">Players</Link>
          <Link to="/teams" className="cta-card">Teams</Link>
        </div>
      </div>
    </div>
  );
}
