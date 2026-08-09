import assert from 'node:assert/strict';
import test from 'node:test';

import { pairSeasonParams, resolvePairSeason } from '../src/lib/pairSeason.js';

test('same-season pair is accepted', () => {
  const result = resolvePairSeason([
    { playerId: '2544', season: '2023-24' },
    { playerId: '203932', season: '2023-24' },
  ]);
  assert.deepEqual(result, { ok: true, seasonA: '2023-24', seasonB: '2023-24', reason: '' });
});

test('cross-season pair keeps both independently selected seasons', () => {
  const result = resolvePairSeason([
    { playerId: '2544', season: '2023-24' },
    { playerId: '203932', season: '2025-26' },
  ]);
  assert.deepEqual(result, { ok: true, seasonA: '2023-24', seasonB: '2025-26', reason: '' });
  assert.deepEqual(
    pairSeasonParams([
      { playerId: '2544', season: '2023-24' },
      { playerId: '203932', season: '2025-26' },
    ]),
    { season_a: '2023-24', season_b: '2025-26' },
  );
});

test('a pair with a missing season is rejected truthfully', () => {
  const result = resolvePairSeason([
    { playerId: '2544', season: '2023-24' },
    { playerId: '203932', season: '' },
  ]);
  assert.equal(result.ok, false);
  assert.match(result.reason, /season for both/);
});
