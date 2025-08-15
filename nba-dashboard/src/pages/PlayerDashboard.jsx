import React from 'react';
import PlayerCard from '../components/PlayerCard.jsx';
import PlayerSelector from '../components/PlayerSelector.jsx';
import '../PlayerCard.css'; // Ensure styles are applied

export default function PlayerDashboard({
  selectedPlayers = [],
  showSelectorIndex = null,
  setShowSelectorIndex = () => {},
  updatePlayer = () => {},
  removePlayer = () => {},
  onAddPlayer = null,
}) {
  return (
    <div className="container py-4" style={{ maxWidth: 1280 }}>
      <div className="row g-4 align-items-stretch">
        {/* Render selected players. Make React remount the PlayerCard whenever the player changes. That resets flipped/backMounted and avoids weird carry-over. */}
        {selectedPlayers.map((p, idx) => (
          <div key={`${p.playerId || 'empty'}-${idx}`} className="col-12 col-md-6 d-flex">
          <div className="position-relative w-100">

              {selectedPlayers.length > 1 && p.playerId && (
                <button
                  type="button"
                  onClick={() => removePlayer(idx)}
                  className="btn btn-sm btn-light position-absolute top-0 end-0 m-2"
                  aria-label="Remove player"
                >
                  ✕
                </button>
              )}

              {(showSelectorIndex === idx) || !p.playerId ? (
                <PlayerSelector onSelect={(player) => updatePlayer(idx, player)} />
              ) : (
                <PlayerCard
                  playerId={p.playerId}
                  playerName={p.playerName}
                  season={p.season}
                  onReplace={() => setShowSelectorIndex(idx)}
                />
              )}
            </div>
          </div>
        ))}

        {selectedPlayers.length < 4 && onAddPlayer && (
          <div className="col-12 col-md-6 d-flex">
            <button
              type="button"
              className="btn btn-outline-primary w-100"
              style={{ minHeight: 140, borderStyle: 'dashed' }}
              onClick={onAddPlayer}
            >
              + Add Player
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
