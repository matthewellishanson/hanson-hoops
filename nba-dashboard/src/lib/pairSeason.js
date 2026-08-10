export function resolvePairSeason(selectedPlayers = []) {
  const pair = Array.isArray(selectedPlayers) ? selectedPlayers : [];
  if (pair.length !== 2 || pair.some((player) => !player?.playerId)) {
    return { ok: false, seasonA: null, seasonB: null, reason: 'Select at least two players to view projected fit.' };
  }
  const seasonA = pair[0].season;
  const seasonB = pair[1].season;
  if (!seasonA || !seasonB) {
    return {
      ok: false,
      seasonA: seasonA || null,
      seasonB: seasonB || null,
      reason: 'Choose a season for both player cards.',
    };
  }
  return { ok: true, seasonA, seasonB, reason: '' };
}

export function pairSeasonParams(selectedPlayers = []) {
  const resolved = resolvePairSeason(selectedPlayers);
  if (!resolved.ok) return null;
  return { season_a: resolved.seasonA, season_b: resolved.seasonB };
}
