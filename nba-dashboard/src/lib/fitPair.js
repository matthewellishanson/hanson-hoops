export function getValidFitCards(selectedPlayers = []) {
  return selectedPlayers.filter((card) => card?.cardId && card?.playerId && card?.season);
}

export function reconcileFitPair(selectedPlayers = [], currentPair = [null, null]) {
  const validCards = getValidFitCards(selectedPlayers);
  const validIds = new Set(validCards.map((card) => card.cardId));
  const next = [
    validIds.has(currentPair?.[0]) ? currentPair[0] : null,
    validIds.has(currentPair?.[1]) ? currentPair[1] : null,
  ];

  if (next[0] && next[0] === next[1]) next[1] = null;

  if (!next[0]) {
    next[0] = validCards.find((card) => card.cardId !== next[1])?.cardId || null;
  }
  if (!next[1]) {
    next[1] = validCards.find((card) => card.cardId !== next[0])?.cardId || null;
  }

  return next;
}

export function selectFitPairPosition(currentPair, position, cardId) {
  if (position !== 0 && position !== 1) return currentPair;
  if (!cardId || currentPair[position] === cardId) return currentPair;

  const otherPosition = position === 0 ? 1 : 0;
  const next = [...currentPair];
  if (currentPair[otherPosition] === cardId) {
    next[position] = cardId;
    next[otherPosition] = currentPair[position] || null;
    return next;
  }

  next[position] = cardId;
  return next;
}

export function getActiveFitCards(selectedPlayers = [], pairIds = [null, null]) {
  const cardsById = new Map(getValidFitCards(selectedPlayers).map((card) => [card.cardId, card]));
  return pairIds.map((cardId) => cardsById.get(cardId) || null);
}
