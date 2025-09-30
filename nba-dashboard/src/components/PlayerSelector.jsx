import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';

// === local helpers ===
function currentNbaSeasonStartYear() {
  const now = new Date();
  if (now.getMonth() > 9 || (now.getMonth() === 9 && now.getDate() >= 15)) {
    return now.getFullYear();
  }
  return now.getFullYear() - 1;
}
function toSeasonLabel(startYear) {
  const endYY = String((startYear + 1) % 100).padStart(2, '0');
  return `${startYear}-${endYY}`;
}
function computeCurrentNbaSeason() {
  return toSeasonLabel(currentNbaSeasonStartYear());
}
function buildSeasonList(count = 30) {
  const start = currentNbaSeasonStartYear();
  const seasons = [];
  for (let i = 0; i < count; i++) seasons.push(toSeasonLabel(start - i));
  return seasons;
}
// =====================

export default function PlayerSelector({ onSelect, initialSeason = null }) {
  const [players, setPlayers] = useState([]);
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [season, setSeason] = useState(initialSeason || computeCurrentNbaSeason());
  const limit = 50;

  useEffect(() => {
    const t = setTimeout(() => {
      api.get('/players', {
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

  const seasons = useMemo(() => buildSeasonList(80), []);

  const handleSubmit = (e) => {
    e.preventDefault();
    const selectedId = e.target.player.value;
    const player = players.find(p => p.id === selectedId);
    if (player) {
      onSelect({ id: player.id, name: player.name, season });
    }
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
