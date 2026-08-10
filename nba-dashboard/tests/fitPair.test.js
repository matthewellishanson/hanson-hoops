import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getActiveFitCards,
  getValidFitCards,
  reconcileFitPair,
  selectFitPairPosition,
} from '../src/lib/fitPair.js';
import { pairSeasonParams } from '../src/lib/pairSeason.js';

const cards = [
  { cardId: 'card-1', playerId: '11', playerName: 'One', season: '2001-02' },
  { cardId: 'card-2', playerId: '22', playerName: 'Two', season: '2002-03' },
  { cardId: 'card-3', playerId: '33', playerName: 'Three', season: '2003-04' },
  { cardId: 'card-4', playerId: '44', playerName: 'Four', season: '2004-05' },
];

test('zero, one, and two valid cards reconcile without duplicating a card', () => {
  assert.deepEqual(reconcileFitPair([], [null, null]), [null, null]);
  assert.deepEqual(reconcileFitPair(cards.slice(0, 1), [null, null]), ['card-1', null]);
  assert.deepEqual(reconcileFitPair(cards.slice(0, 2), [null, null]), ['card-1', 'card-2']);
});

test('three or four cards default to the first two in stable dashboard order', () => {
  assert.deepEqual(reconcileFitPair(cards.slice(0, 3)), ['card-1', 'card-2']);
  assert.deepEqual(reconcileFitPair(cards), ['card-1', 'card-2']);
});

test('either pair position can select any card and selecting the opposite card swaps positions', () => {
  assert.deepEqual(selectFitPairPosition(['card-1', 'card-2'], 0, 'card-3'), ['card-3', 'card-2']);
  assert.deepEqual(selectFitPairPosition(['card-1', 'card-2'], 1, 'card-4'), ['card-1', 'card-4']);
  assert.deepEqual(selectFitPairPosition(['card-1', 'card-2'], 0, 'card-2'), ['card-2', 'card-1']);
  assert.deepEqual(selectFitPairPosition(['card-1', 'card-2'], 1, 'card-1'), ['card-2', 'card-1']);
});

test('adding cards and clearing a non-active card preserve the active pair', () => {
  assert.deepEqual(reconcileFitPair(cards, ['card-2', 'card-1']), ['card-2', 'card-1']);
  assert.deepEqual(reconcileFitPair([cards[0], cards[1], cards[3]], ['card-2', 'card-1']), ['card-2', 'card-1']);
});

test('an invalid or removed active card is replaced without moving the surviving active card', () => {
  assert.deepEqual(
    reconcileFitPair([cards[0], cards[1], cards[3]], ['card-3', 'card-4']),
    ['card-1', 'card-4'],
  );
  assert.deepEqual(
    reconcileFitPair([cards[0], cards[1], cards[2]], ['card-3', 'card-4']),
    ['card-3', 'card-1'],
  );
  assert.deepEqual(
    reconcileFitPair([{ ...cards[0], playerId: '' }, cards[1], cards[2]], ['card-1', 'card-2']),
    ['card-3', 'card-2'],
  );
});

test('fewer than two valid cards retain a surviving card in its existing pair position', () => {
  assert.deepEqual(reconcileFitPair([cards[1]], ['card-1', 'card-2']), [null, 'card-2']);
  assert.deepEqual(getActiveFitCards([cards[1]], [null, 'card-2']), [null, cards[1]]);
});

test('card identity survives player and season edits and keeps request values aligned', () => {
  const editedCards = [
    { ...cards[0], playerId: '99', playerName: 'Replacement', season: '2011-12' },
    { ...cards[1], season: '2020-21' },
    cards[2],
  ];
  const pairIds = reconcileFitPair(editedCards, ['card-1', 'card-2']);
  const activeCards = getActiveFitCards(editedCards, pairIds);

  assert.deepEqual(pairIds, ['card-1', 'card-2']);
  assert.deepEqual(activeCards.map((card) => card.playerId), ['99', '22']);
  assert.deepEqual(pairSeasonParams(activeCards), { season_a: '2011-12', season_b: '2020-21' });
});

test('distinct cards allow the same player in independently selected seasons', () => {
  const samePlayerCards = [
    { cardId: 'card-1', playerId: '2544', playerName: 'LeBron James', season: '2012-13' },
    { cardId: 'card-2', playerId: '2544', playerName: 'LeBron James', season: '2023-24' },
  ];
  const pairIds = reconcileFitPair(samePlayerCards);
  const activeCards = getActiveFitCards(samePlayerCards, pairIds);

  assert.deepEqual(pairIds, ['card-1', 'card-2']);
  assert.deepEqual(pairSeasonParams(activeCards), { season_a: '2012-13', season_b: '2023-24' });
});

test('cards without a complete player-season selection are not valid fit options', () => {
  assert.deepEqual(getValidFitCards([
    cards[0],
    { ...cards[1], season: '' },
    { ...cards[2], playerId: '' },
  ]), [cards[0]]);
});
