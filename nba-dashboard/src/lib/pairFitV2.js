export function getValidPairFitCards(selectedPlayers = []) {
  return selectedPlayers.filter(
    (card) => card?.cardId && card?.playerId && card?.playerName && card?.season,
  );
}

function pairKey(cardA, cardB) {
  return JSON.stringify([cardA.cardId, cardB.cardId].sort());
}

export function buildUnorderedPairOptions(selectedPlayers = []) {
  const cards = getValidPairFitCards(selectedPlayers);
  const options = [];
  for (let left = 0; left < cards.length; left += 1) {
    for (let right = left + 1; right < cards.length; right += 1) {
      const cardA = cards[left];
      const cardB = cards[right];
      if (String(cardA.playerId) === String(cardB.playerId)) continue;
      options.push({
        key: pairKey(cardA, cardB),
        cards: [cardA, cardB],
        label: `${cardA.playerName} (${cardA.season}) + ${cardB.playerName} (${cardB.season})`,
      });
    }
  }
  return options;
}

export function reconcilePairOption(options = [], currentKey = '') {
  if (options.some((option) => option.key === currentKey)) return currentKey;
  return options[0]?.key || '';
}

export function buildPairFitV2Request(option) {
  if (!option?.cards || option.cards.length !== 2) {
    return { ok: false, reasonCode: 'pair_unavailable', message: 'Select two different players.' };
  }
  const [playerA, playerB] = option.cards;
  if (String(playerA.playerId) === String(playerB.playerId)) {
    return { ok: false, reasonCode: 'same_player', message: 'Pair Fit v2 requires two different players.' };
  }
  if (playerA.season !== playerB.season) {
    return {
      ok: false,
      reasonCode: 'cross_season_pair',
      message: 'Pair Fit v2 currently requires both player cards to use the same target season.',
    };
  }

  const ids = [String(playerA.playerId), String(playerB.playerId)].sort(
    (a, b) => Number(a) - Number(b) || a.localeCompare(b),
  );
  const targetSeason = playerA.season;
  return {
    ok: true,
    requestKey: JSON.stringify([ids, targetSeason]),
    url: `/fit/v2/pair/${encodeURIComponent(ids[0])}/${encodeURIComponent(ids[1])}`,
    params: { target_season: targetSeason },
  };
}

export function validatePairFitV2Payload(payload) {
  if (!payload || typeof payload !== 'object' || typeof payload.supported !== 'boolean') {
    throw new Error('Pair Fit v2 returned a malformed response.');
  }
  if (!payload.supported) {
    if (typeof payload.reason_code !== 'string' || typeof payload.message !== 'string') {
      throw new Error('Pair Fit v2 returned a malformed refusal.');
    }
    return payload;
  }

  const strings = [
    'model_name',
    'model_version',
    'output_definition',
    'units',
    'display_value',
    'confidence',
    'confidence_meaning',
    'error_disclosure',
  ];
  if (
    strings.some((field) => typeof payload[field] !== 'string')
    || typeof payload.projected_net_rating !== 'number'
    || !Number.isFinite(payload.projected_net_rating)
    || typeof payload.typical_final_test_error !== 'number'
    || !Number.isFinite(payload.typical_final_test_error)
    || !['standard', 'lower'].includes(payload.confidence)
  ) {
    throw new Error('Pair Fit v2 returned a malformed response.');
  }
  return payload;
}

export const initialPairFitRequestState = {
  requestKey: null,
  status: 'idle',
  data: null,
  error: '',
};

export function pairFitRequestReducer(state, action) {
  if (action.type === 'reset') return initialPairFitRequestState;
  if (action.type === 'begin') {
    return { requestKey: action.requestKey, status: 'loading', data: null, error: '' };
  }
  if (action.requestKey !== state.requestKey) return state;
  if (action.type === 'resolve') {
    return { ...state, status: 'complete', data: action.data, error: '' };
  }
  if (action.type === 'fail') {
    return { ...state, status: 'error', data: null, error: action.error };
  }
  return state;
}
