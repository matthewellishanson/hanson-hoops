import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import {
  buildPairFitV2Request,
  buildUnorderedPairOptions,
  initialPairFitRequestState,
  pairFitRequestReducer,
  reconcilePairOption,
  validatePairFitV2Payload,
} from '../src/lib/pairFitV2.js';

const cards = [
  { cardId: 'card-1', playerId: '2544', playerName: 'LeBron James', season: '2026-27' },
  { cardId: 'card-2', playerId: '203932', playerName: 'Aaron Gordon', season: '2026-27' },
  { cardId: 'card-3', playerId: '1630162', playerName: 'Anthony Edwards', season: '2026-27' },
  { cardId: 'card-4', playerId: '1629029', playerName: 'Luka Doncic', season: '2026-27' },
];

const supportedPayload = {
  supported: true,
  model_name: 'Pair Fit v2',
  model_version: 'pair-fit-v2.0.0',
  output_definition: 'projected shared-court team NET_RATING',
  units: 'points per 100 possessions',
  projected_net_rating: 1.234,
  display_value: '+1',
  confidence: 'standard',
  confidence_meaning: 'history completeness, not probability',
  typical_final_test_error: 7.7891668891345205,
  error_disclosure: 'Typical final-test error: approximately 7.8 points per 100 possessions.',
};

test('fewer than two complete cards produce no Pair Fit option or request', () => {
  assert.deepEqual(buildUnorderedPairOptions([]), []);
  assert.deepEqual(buildUnorderedPairOptions(cards.slice(0, 1)), []);
  assert.equal(buildPairFitV2Request(null).ok, false);
});

test('exactly two same-season cards automatically build the v2 endpoint request', () => {
  const options = buildUnorderedPairOptions(cards.slice(0, 2));
  assert.equal(options.length, 1);
  const request = buildPairFitV2Request(options[0]);
  assert.deepEqual(request, {
    ok: true,
    requestKey: JSON.stringify([['2544', '203932'], '2026-27']),
    url: '/fit/v2/pair/2544/203932',
    params: { target_season: '2026-27' },
  });
});

test('cross-season pair is refused before an API request is formed', () => {
  const options = buildUnorderedPairOptions([
    cards[0],
    { ...cards[1], season: '2025-26' },
  ]);
  const request = buildPairFitV2Request(options[0]);
  assert.equal(request.ok, false);
  assert.equal(request.reasonCode, 'cross_season_pair');
  assert.match(request.message, /same target season/);
  assert.equal('url' in request, false);
});

test('three and four cards create each unordered pair exactly once', () => {
  assert.equal(buildUnorderedPairOptions(cards.slice(0, 3)).length, 3);
  const options = buildUnorderedPairOptions(cards);
  assert.equal(options.length, 6);
  assert.equal(new Set(options.map((option) => option.key)).size, 6);
  assert.equal(reconcilePairOption(options, options[4].key), options[4].key);
  assert.equal(reconcilePairOption(options, 'removed-pair'), options[0].key);
});

test('same-player cards never become a selectable pair', () => {
  const options = buildUnorderedPairOptions([
    cards[0],
    { ...cards[1], playerId: cards[0].playerId, playerName: cards[0].playerName },
  ]);
  assert.deepEqual(options, []);
});

test('request state clears stale data as soon as a new request begins', () => {
  const resolved = {
    requestKey: 'old',
    status: 'complete',
    data: supportedPayload,
    error: '',
  };
  const loading = pairFitRequestReducer(resolved, { type: 'begin', requestKey: 'new' });
  assert.deepEqual(loading, {
    requestKey: 'new',
    status: 'loading',
    data: null,
    error: '',
  });
});

test('stale request completions cannot replace the active result', () => {
  const loading = pairFitRequestReducer(initialPairFitRequestState, {
    type: 'begin',
    requestKey: 'new',
  });
  const afterStale = pairFitRequestReducer(loading, {
    type: 'resolve',
    requestKey: 'old',
    data: supportedPayload,
  });
  assert.deepEqual(afterStale, loading);
});

test('supported standard and lower-confidence responses validate', () => {
  assert.equal(validatePairFitV2Payload(supportedPayload).confidence, 'standard');
  assert.equal(
    validatePairFitV2Payload({ ...supportedPayload, confidence: 'lower' }).confidence,
    'lower',
  );
});

test('structured refusals validate and malformed responses fail', () => {
  const refusal = {
    supported: false,
    reason_code: 'target_season_after_supported_range',
    message: 'Pair Fit currently supports target seasons through 2026-27.',
  };
  assert.equal(validatePairFitV2Payload(refusal).reason_code, refusal.reason_code);
  assert.throws(
    () => validatePairFitV2Payload({ supported: true, display_value: '+1' }),
    /malformed response/,
  );
});

test('network failure state removes data and keeps an accessible message', () => {
  const loading = pairFitRequestReducer(initialPairFitRequestState, {
    type: 'begin',
    requestKey: 'request',
  });
  const failed = pairFitRequestReducer(loading, {
    type: 'fail',
    requestKey: 'request',
    error: 'Pair Fit v2 is temporarily unavailable.',
  });
  assert.equal(failed.status, 'error');
  assert.equal(failed.data, null);
  assert.match(failed.error, /temporarily unavailable/);
});

test('normal Player Comparisons flow renders only the compact v2 component', () => {
  const dashboard = fs.readFileSync(new URL('../src/pages/PlayerDashboard.jsx', import.meta.url), 'utf8');
  const component = fs.readFileSync(new URL('../src/components/PairFitSummaryCard.jsx', import.meta.url), 'utf8');
  assert.match(dashboard, /PairFitSummaryCard/);
  assert.doesNotMatch(dashboard, /PlayerFitPanel/);
  assert.doesNotMatch(component, /form-range|primary handler|Fit score|Top positive drivers|risk flags/i);
  assert.match(component, /About this projection/);
});
