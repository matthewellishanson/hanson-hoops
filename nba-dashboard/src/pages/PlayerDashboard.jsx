import React from 'react';
import PlayerCard from '../components/PlayerCard.jsx';
import PlayerSelector from '../components/PlayerSelector.jsx';

// helper to chunk into rows of 2
function chunk2(arr) {
  const rows = [];
  for (let i = 0; i < arr.length; i += 2) rows.push(arr.slice(i, i + 2));
  return rows;
}

export default function PlayerDashboard({
  selectedPlayers = [],          // array of { playerId, playerName, season }
  showSelectorIndex = null,      // which slot (index) is currently showing the selector UI
  setShowSelectorIndex = () => {},
  updatePlayer = () => {},       // callback(idx, { id, name, season? })
  removePlayer = () => {},       // callback(idx)
  onAddPlayer = null,            // callback() — only shown when passed and < 4 players
}) {
  const count = selectedPlayers.length;

  console.log('[PD] count =', count);

  // Decide target card height based on how many players are on screen.
  // Using viewport units helps two rows fit without scrolling.
  const cardHeight =
    count <= 1 ? '62vh' :       // 1 card: make it big and centered
    count === 2 ? '54vh' :      // 2 cards: a bit shorter so they fit side by side
    '46vh';                     // 3 or 4 cards: two rows, each card ~half the viewport

  console.log('[PD] cardHeight =', cardHeight);

  // Turn [p0, p1, p2, p3] into [[p0,p1],[p2,p3]]
  const rows = chunk2(selectedPlayers);
  console.log('[PD] rows =', rows);

  return (
    <div className="container py-4 min-vh-100" style={{ maxWidth: 1280 }}>
      {/* Loop each row (two cards per row) */}
      {rows.map((row, rIndex) => {
  const isSingle = row.length === 1;
  console.log('[PD] row', rIndex, 'length', row.length);

  return (
    <div
      key={rIndex}
      className={`row g-4 align-items-stretch ${isSingle ? 'justify-content-center' : ''}`}
    >
      {row.map((p, idxInRow) => {
        const idx = rIndex * 2 + idxInRow;

        // ✅ Key now includes season so replacing same player w/ new season remounts
        const wrapperKey = `${p.playerId || 'empty'}-${p.season || 'na'}-${idx}`;

        const colClasses = isSingle
          ? 'col-12 col-md-8 col-lg-6 d-flex'
          : 'col-12 col-md-6 d-flex';

        console.log('[PD] idx =', idx, 'colClasses =', colClasses, 'p =', p);

        return (
          <div key={wrapperKey} className={colClasses}>
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
                <PlayerSelector initialSeason={p.season} onSelect={(player) => updatePlayer(idx, player)} />
              ) : (
                <PlayerCard
                  style={{ '--card-h': cardHeight }}
                  playerId={p.playerId}
                  playerName={p.playerName}
                  season={p.season}
                  onReplace={() => setShowSelectorIndex(idx)}
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
})}

      {/* “Add Player” tile (optional). 
          Shown only if you provided onAddPlayer AND we have fewer than 4 players. 
          For odd counts (1 or 3), we center the tile so the grid looks balanced. */}
      {selectedPlayers.length < 4 && onAddPlayer && (
        <div className={`row g-4 ${selectedPlayers.length % 2 === 0 ? '' : 'justify-content-center'}`}>
          <div className={selectedPlayers.length % 2 === 0 ? 'col-12 col-md-6 d-flex' : 'col-12 col-md-8 col-lg-6 d-flex'}>
            <button
              type="button"
              className="btn btn-outline-primary w-100"
              style={{ minHeight: 140, borderStyle: 'dashed' }}
              onClick={onAddPlayer}
            >
              + Add Player
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
