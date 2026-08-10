import React, { useEffect, useMemo, useState } from 'react';
import { api, apiErrorMessage } from '../lib/api';
import {
  getActiveFitCards,
  getValidFitCards,
  reconcileFitPair,
  selectFitPairPosition,
} from '../lib/fitPair';
import { resolvePairSeason } from '../lib/pairSeason';

function axisEntries(axes = {}) {
  // Keep axis ordering stable across cards for visual scan consistency.
  return [
    ['Creation', axes.creation_load],
    ['Scoring', axes.scoring_pressure],
    ['Spacing', axes.spacing_gravity],
    ['Security', axes.ball_security],
    ['Disruption', axes.disruption],
    ['Rim', axes.rim_protection],
    ['Rebounding', axes.rebounding],
  ];
}

function AxisBars({ title, axes }) {
  const rows = axisEntries(axes);
  return (
    <div className="col-12 col-lg-6">
      <h6 className="mb-2">{title}</h6>
      {rows.map(([label, value]) => {
        const v = Number(value || 0);
        return (
          <div key={label} className="mb-2">
            <div className="d-flex justify-content-between">
              <small>{label}</small>
              <small>{v.toFixed(1)}</small>
            </div>
            <div className="progress" role="progressbar" aria-valuenow={v} aria-valuemin="0" aria-valuemax="100">
              <div className="progress-bar" style={{ width: `${Math.max(0, Math.min(100, v))}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function PlayerFitPanel({ selectedPlayers = [] }) {
  const validCards = useMemo(() => getValidFitCards(selectedPlayers), [selectedPlayers]);
  const [pairIds, setPairIds] = useState([null, null]);
  const reconciledPairIds = useMemo(
    () => reconcileFitPair(validCards, pairIds),
    [validCards, pairIds],
  );
  const chosen = useMemo(
    () => getActiveFitCards(validCards, reconciledPairIds),
    [validCards, reconciledPairIds],
  );
  const hasPair = chosen.every(Boolean);
  const seasonPolicy = useMemo(() => resolvePairSeason(chosen), [chosen]);
  const cardOptions = useMemo(() => validCards.map((card) => {
    const cardPosition = selectedPlayers.findIndex((candidate) => candidate.cardId === card.cardId) + 1;
    return {
      card,
      label: `Card ${cardPosition} — ${card.playerName || 'Selected player'} (${card.season})`,
    };
  }), [selectedPlayers, validCards]);
  const labelsById = useMemo(
    () => new Map(cardOptions.map(({ card, label }) => [card.cardId, label])),
    [cardOptions],
  );
  const excludedCards = cardOptions.filter(({ card }) => !reconciledPairIds.includes(card.cardId));
  const activeLabelA = labelsById.get(reconciledPairIds[0]) || 'No valid card selected';
  const activeLabelB = labelsById.get(reconciledPairIds[1]) || 'No valid card selected';
  const playerAId = chosen[0]?.playerId || null;
  const playerBId = chosen[1]?.playerId || null;
  const seasonA = seasonPolicy.seasonA;
  const seasonB = seasonPolicy.seasonB;

  useEffect(() => {
    setPairIds((current) => {
      const next = reconcileFitPair(validCards, current);
      return next[0] === current[0] && next[1] === current[1] ? current : next;
    });
  }, [validCards]);

  const selectPairCard = (position, cardId) => {
    setPairIds((current) => {
      const currentValidPair = reconcileFitPair(validCards, current);
      return selectFitPairPosition(currentValidPair, position, cardId);
    });
  };

  const [offense, setOffense] = useState(1.0);
  const [defense, setDefense] = useState(1.0);
  const [spacers, setSpacers] = useState(1.0);
  const [rebounding, setRebounding] = useState(1.0);
  const [primaryHandler, setPrimaryHandler] = useState('auto');

  const requestKey = hasPair && seasonPolicy.ok
    ? JSON.stringify([
        reconciledPairIds,
        playerAId,
        playerBId,
        seasonA,
        seasonB,
        offense,
        defense,
        spacers,
        rebounding,
        primaryHandler,
      ])
    : null;
  const [loadingRequest, setLoadingRequest] = useState(null);
  const [errorResult, setErrorResult] = useState(null);
  const [payloadResult, setPayloadResult] = useState(null);
  const loading = Boolean(requestKey && loadingRequest === requestKey);
  const error = errorResult?.requestKey === requestKey ? errorResult.message : '';
  const payload = payloadResult?.requestKey === requestKey ? payloadResult.data : null;

  useEffect(() => {
    if (!requestKey) return;

    const params = {
      season_a: seasonA,
      season_b: seasonB,
      min_minutes: 300,
      offense,
      defense,
      spacers,
      rebounding,
      primary_handler: primaryHandler,
    };

    let alive = true;
    // Abort in-flight requests when sliders/selection change to prevent stale updates.
    const controller = new AbortController();
    setLoadingRequest(requestKey);
    setErrorResult(null);

    api.get(`/fit/pair/${playerAId}/${playerBId}`, {
      params,
      // First model call can be slow while backend builds feature caches.
      timeout: 90000,
      signal: controller.signal,
    })
      .then((res) => {
        if (!alive) return;
        setPayloadResult({ requestKey, data: res.data || null });
      })
      .catch((e) => {
        if (!alive) return;
        // Ignore expected cancellation noise from re-renders or input changes.
        if (e?.code === 'ERR_CANCELED') return;
        setPayloadResult(null);
        setErrorResult({
          requestKey,
          message: apiErrorMessage(e, 'Could not load projected fit.'),
        });
      })
      .finally(() => {
        if (alive) setLoadingRequest(null);
      });

    return () => { alive = false; controller.abort(); };
  }, [requestKey, playerAId, playerBId, seasonA, seasonB, offense, defense, spacers, rebounding, primaryHandler]);

  return (
    <div className="fit-panel card shadow-sm mb-4">
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
          <div>
            <h4 className="mb-1">Projected Pair Fit</h4>
            <p className="text-muted mb-0">Deterministic style compatibility model, not observed on-court synergy.</p>
          </div>
          {payload?.weight_version && <span className="badge text-bg-light">{payload.weight_version}</span>}
        </div>

        {validCards.length >= 2 && (
          <div className="border rounded p-3 mb-3" aria-label="Active fit pair">
            <div className="row g-3">
              <div className="col-12 col-md-6">
                <label className="form-label fw-semibold" htmlFor="fit-pair-card-a">Pair position A</label>
                <select
                  id="fit-pair-card-a"
                  className="form-select"
                  value={reconciledPairIds[0] || ''}
                  aria-describedby="fit-pair-help"
                  onChange={(event) => selectPairCard(0, event.target.value)}
                >
                  {cardOptions.map(({ card, label }) => (
                    <option key={card.cardId} value={card.cardId}>{label}</option>
                  ))}
                </select>
              </div>
              <div className="col-12 col-md-6">
                <label className="form-label fw-semibold" htmlFor="fit-pair-card-b">Pair position B</label>
                <select
                  id="fit-pair-card-b"
                  className="form-select"
                  value={reconciledPairIds[1] || ''}
                  aria-describedby="fit-pair-help"
                  onChange={(event) => selectPairCard(1, event.target.value)}
                >
                  {cardOptions.map(({ card, label }) => (
                    <option key={card.cardId} value={card.cardId}>{label}</option>
                  ))}
                </select>
              </div>
            </div>
            <p id="fit-pair-help" className="small text-muted mt-2 mb-2">
              Pair order is explicit. Choosing the card already in the other position swaps positions A and B.
            </p>
            <div className="small">
              <strong>Active pair:</strong> A — {activeLabelA}; B — {activeLabelB}.
            </div>
            {excludedCards.length > 0 && (
              <div className="small text-muted mt-1">
                <strong>Not included in this pairwise analysis:</strong>{' '}
                {excludedCards.map(({ label }) => label).join('; ')}.
              </div>
            )}
            <div className="small text-muted mt-1">
              The projected score applies only to this ordered pair, not the full set of selected cards.
            </div>
          </div>
        )}

        {!hasPair && (
          <div className="alert alert-info mb-0">
            Select two valid player-season cards to view projected fit.
          </div>
        )}

        {hasPair && !seasonPolicy.ok && (
          <div className="alert alert-warning mb-0">{seasonPolicy.reason}</div>
        )}

        {hasPair && seasonPolicy.ok && (
          <>
            <div className="row g-3 mb-3">
              <div className="col-12 col-md-4">
                <label className="form-label">Offense emphasis ({offense.toFixed(1)}x)</label>
                <input className="form-range" type="range" min="0.5" max="1.8" step="0.1" value={offense} onChange={(e) => setOffense(Number(e.target.value))} />
              </div>
              <div className="col-12 col-md-4">
                <label className="form-label">Defense emphasis ({defense.toFixed(1)}x)</label>
                <input className="form-range" type="range" min="0.5" max="1.8" step="0.1" value={defense} onChange={(e) => setDefense(Number(e.target.value))} />
              </div>
              <div className="col-12 col-md-4">
                <label className="form-label">Spacers emphasis ({spacers.toFixed(1)}x)</label>
                <input className="form-range" type="range" min="0.5" max="1.8" step="0.1" value={spacers} onChange={(e) => setSpacers(Number(e.target.value))} />
              </div>
              <div className="col-12 col-md-4">
                <label className="form-label">Rebounding emphasis ({rebounding.toFixed(1)}x)</label>
                <input className="form-range" type="range" min="0.5" max="1.8" step="0.1" value={rebounding} onChange={(e) => setRebounding(Number(e.target.value))} />
              </div>
              <div className="col-12 col-md-4">
                <label className="form-label">Primary handler assumption</label>
                <select className="form-select" value={primaryHandler} onChange={(e) => setPrimaryHandler(e.target.value)}>
                  <option value="auto">Auto</option>
                  <option value="a">A — {activeLabelA}</option>
                  <option value="b">B — {activeLabelB}</option>
                </select>
              </div>
            </div>

            {loading && <div className="text-muted">Loading projected fit...</div>}
            {!!error && <div className="alert alert-warning">{error}</div>}

            {payload && !loading && !error && (
              <>
                <div className="row g-3 align-items-stretch mb-3">
                  <div className="col-12 col-md-4">
                    <div className="border rounded p-3 h-100">
                      <div className="text-muted">Fit score</div>
                      <div className="display-6 fw-bold">{Number(payload.fit_score || 0).toFixed(1)}</div>
                      <div className={`badge ${payload.confidence?.label === 'high' ? 'text-bg-success' : payload.confidence?.label === 'medium' ? 'text-bg-warning' : 'text-bg-secondary'}`}>
                        Confidence: {payload.confidence?.label || 'low'} ({Number(payload.confidence?.score || 0).toFixed(1)})
                      </div>
                    </div>
                  </div>
                  <div className="col-12 col-md-4">
                    <div className="border rounded p-3 h-100">
                      <div className="text-muted mb-2">Top positive drivers</div>
                      <ul className="mb-0">
                        {(payload.drivers_positive || []).map((d) => (
                          <li key={d.component}>
                            {d.component.replaceAll('_', ' ')} (+{Number(d.impact || 0).toFixed(2)})
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  <div className="col-12 col-md-4">
                    <div className="border rounded p-3 h-100">
                      <div className="text-muted mb-2">Top risk flags</div>
                      <ul className="mb-0">
                        {(payload.risks || []).length === 0 && <li>No major flags triggered.</li>}
                        {(payload.risks || []).map((r, i) => (
                          <li key={`${r}-${i}`}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="row g-3">
                  <AxisBars title={`${payload.player_a?.name || 'Player A'} (${payload.player_a?.season || seasonPolicy.seasonA})`} axes={payload.player_a?.axes || {}} />
                  <AxisBars title={`${payload.player_b?.name || 'Player B'} (${payload.player_b?.season || seasonPolicy.seasonB})`} axes={payload.player_b?.axes || {}} />
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
