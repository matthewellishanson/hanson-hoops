import React, { useMemo, useState } from 'react';
import TeamCard from '../components/TeamCard.jsx';
import TeamSelector from '../components/TeamSelector.jsx';

// chunk into rows of 2 (same helper you use on players)
function chunk2(arr) {
  const rows = [];
  for (let i = 0; i < arr.length; i += 2) rows.push(arr.slice(i, i + 2));
  return rows;
}

// Helpers to build season label like "2024-25"
function currentNbaSeasonStartYear() {
  const now = new Date();
  return now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1;
}
function toSeasonLabel(startYear) {
  const endYY = String((startYear + 1) % 100).padStart(2, '0');
  return `${startYear}-${endYY}`;
}
const DEFAULT_SEASON = toSeasonLabel(currentNbaSeasonStartYear());

// Default = Philadelphia 76ers (PHI)
const DEFAULT_TEAM = { teamId: '1610612755', teamName: 'Philadelphia 76ers', season: DEFAULT_SEASON };

export default function TeamDashboard() {
  const [selectedTeams, setSelectedTeams] = useState([DEFAULT_TEAM]);
  const [showSelectorIndex, setShowSelectorIndex] = useState(null);

  const count = selectedTeams.length;
  const cardHeight =
    count <= 1 ? '62vh' :
    count === 2 ? '54vh' :
    '46vh';

  const rows = useMemo(() => chunk2(selectedTeams), [selectedTeams]);

  const updateTeam = (idx, team) => {
    setSelectedTeams(prev => {
      const next = [...prev];
      next[idx] = {
        teamId: team.id,
        teamName: team.name,
        season: team.season || prev[idx]?.season || DEFAULT_SEASON,
      };
      return next;
    });
    setShowSelectorIndex(null);
  };

  const removeTeam = (idx) => {
    setSelectedTeams(prev => prev.filter((_, i) => i !== idx));
    setShowSelectorIndex(null);
  };

  const onAddTeam = () => {
    setSelectedTeams(prev => {
      if (prev.length >= 4) return prev;
      const next = [...prev, { teamId: '', teamName: '', season: DEFAULT_SEASON }];
      setShowSelectorIndex(next.length - 1);
      return next;
    });
  };

  return (
    <div className="container py-4 min-vh-100" style={{ maxWidth: 1280 }}>
      {rows.map((row, rIndex) => {
        const isSingle = row.length === 1;
        return (
          <div
            key={rIndex}
            className={`row g-4 align-items-stretch ${isSingle ? 'justify-content-center' : ''}`}
          >
            {row.map((t, idxInRow) => {
              const idx = rIndex * 2 + idxInRow;
              const key = `${t.teamId || 'empty'}-${t.season || 'na'}-${idx}`;
              const colClasses = isSingle ? 'col-12 col-md-8 col-lg-6 d-flex' : 'col-12 col-md-6 d-flex';

              return (
                <div key={key} className={colClasses}>
                  <div className="position-relative w-100">
                    {selectedTeams.length > 1 && t.teamId && (
                      <button
                        type="button"
                        onClick={() => removeTeam(idx)}
                        className="btn btn-sm btn-light position-absolute top-0 end-0 m-2"
                        aria-label="Remove team"
                      >
                        ✕
                      </button>
                    )}

                    {(showSelectorIndex === idx) || !t.teamId ? (
                      <TeamSelector
                        initialSeason={t.season}
                        onSelect={(team) => updateTeam(idx, team)}
                      />
                    ) : (
                      <TeamCard
                        style={{ '--card-h': cardHeight }}
                        teamId={t.teamId}
                        teamName={t.teamName}
                        season={t.season}
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

      {/* Add Team tile */}
      {selectedTeams.length < 4 && (
        <div className={`row g-4 ${selectedTeams.length % 2 === 0 ? '' : 'justify-content-center'}`}>
          <div className={selectedTeams.length % 2 === 0 ? 'col-12 col-md-6 d-flex' : 'col-12 col-md-8 col-lg-6 d-flex'}>
            <button
              type="button"
              className="btn btn-outline-primary w-100"
              style={{ minHeight: 140, borderStyle: 'dashed' }}
              onClick={onAddTeam}
            >
              + Add Team
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
