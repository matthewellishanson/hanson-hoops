import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

// Season helpers (same pattern you used elsewhere)
function currentNbaSeasonStartYear() {
  const now = new Date();
  // Use October 15th as the season start date
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
function buildSeasonList(count = 80) {
  const start = currentNbaSeasonStartYear();
  const seasons = [];
  for (let i = 0; i < count; i++) seasons.push(toSeasonLabel(start - i));
  return seasons;
}

export default function TeamSelector({ onSelect, initialSeason = null }) {
  const [teams, setTeams] = useState([]);
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [season, setSeason] = useState(initialSeason || computeCurrentNbaSeason());
  const limit = 50;

  useEffect(() => {
    const t = setTimeout(() => {
      axios.get('http://localhost:8000/teams', {
        params: {
          search: search || undefined,
          limit,
          offset,
          sort: 'name',
          order: 'asc',
        },
      })
      .then(res => {
        setTeams(res.data.items || []);
        setTotal(res.data.total || 0);
      })
      .catch(err => console.error('Error fetching teams:', err));
    }, 250);
    return () => clearTimeout(t);
  }, [search, offset]);

  const seasons = useMemo(() => buildSeasonList(80), []);

  const handleSubmit = (e) => {
    e.preventDefault();
    const selectedId = e.target.team.value;
    const t = teams.find(team => team.id === selectedId);
    if (t) onSelect({ id: t.id, name: t.name, season });
  };

  return (
    <form onSubmit={handleSubmit} className="d-flex flex-column gap-2 w-100">
      <input
        className="form-control"
        placeholder="Search team…"
        value={search}
        onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
      />

      <select name="team" className="form-select" required size={10}>
        {teams.map(t => (
          <option key={t.id} value={t.id}>
            {t.name}{t.tri_code ? ` (${t.tri_code})` : ''}
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
          {Math.min(offset + 1, total)}–{Math.min(offset + teams.length, total)} of {total}
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

      <button type="submit" className="btn btn-primary">Add Team</button>
    </form>
  );
}
