import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

export default function PlayerSelector({ onSelect, initialSeason = null }) {
  const [players, setPlayers] = useState([]);
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [season, setSeason] = useState(initialSeason || computeCurrentNbaSeason()); // 👈
  const limit = 50;

  useEffect(() => {
    const t = setTimeout(() => {
      axios.get('http://localhost:8000/players', {
        params: {
          search: search || undefined,
          active_only: false,
          limit,
          offset,
          sort: 'name',
          order: 'asc',
        },
      })
      .then(res => {
        setPlayers(res.data.items || []);
        setTotal(res.data.total || 0);
      })
      .catch(err => console.error('Error fetching players:', err));
    }, 250);
    return () => clearTimeout(t);
  }, [search, offset]);

  const seasons = useMemo(() => buildSeasonList(30), []); // last 30 seasons

  const handleSubmit = (e) => {
    e.preventDefault();
    const selectedId = e.target.player.value;
    const player = players.find(p => p.id === selectedId);
    if (player) onSelect({ id: player.id, name: player.name, season }); // 👈 include season
  };

  return (
    <form onSubmit={handleSubmit} className="d-flex flex-column gap-2 w-100">
      <input
        className="form-control"
        placeholder="Search any player (all-time)…"
        value={search}
        onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
      />

      <select name="player" className="form-select" required size={10}>
        {players.map(p => (
          <option key={p.id} value={p.id}>
            {p.name}{p.is_active ? ' (active)' : ''}
          </option>
        ))}
      </select>

      {/* Season selector */}
      <div className="d-flex gap-2 align-items-center">
        <label className="mb-0">Season:</label>
        <select
          className="form-select"
          value={season}
          onChange={(e) => setSeason(e.target.value)}
        >
          {seasons.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Pager */}
      <div className="d-flex justify-content-between align-items-center">
        <button
          type="button"
          className="btn btn-outline-secondary"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - limit))}
        >
          ◀ Prev
        </button>
        <small>
          {Math.min(offset + 1, total)}–{Math.min(offset + players.length, total)} of {total}
        </small>
        <button
          type="button"
          className="btn btn-outline-secondary"
          disabled={offset + limit >= total}
          onClick={() => setOffset(offset + limit)}
        >
          Next ▶
        </button>
      </div>

      <button type="submit" className="btn btn-primary">Add Player</button>
    </form>
  );
}

/* Helpers */
function computeCurrentNbaSeason() {
  // NBA season starts ~Oct; if month >= 8 (Aug) treat as new season’s start year
  const now = new Date();
  const y = now.getFullYear();
  const startYear = now.getMonth() >= 8 ? y : y - 1;
  const end2 = String((startYear + 1) % 100).padStart(2, '0');
  return `${startYear}-${end2}`; // e.g., "2024-25"
}

function buildSeasonList(n = 25) {
  const list = [];
  let cur = computeCurrentNbaSeason(); // "YYYY-YY"
  let y = parseInt(cur.slice(0, 4), 10);
  for (let i = 0; i < n; i++) {
    const end2 = String((y + 1) % 100).padStart(2, '0');
    list.push(`${y}-${end2}`);
    y -= 1;
  }
  return list;
}