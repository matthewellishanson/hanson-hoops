import React, { useEffect, useMemo, useReducer, useState } from 'react';
import { api, apiErrorMessage } from '../lib/api';
import {
  buildPairFitV2Request,
  buildUnorderedPairOptions,
  getValidPairFitCards,
  initialPairFitRequestState,
  pairFitRequestReducer,
  reconcilePairOption,
  validatePairFitV2Payload,
} from '../lib/pairFitV2';

export default function PairFitSummaryCard({ selectedPlayers = [] }) {
  const validCards = useMemo(() => getValidPairFitCards(selectedPlayers), [selectedPlayers]);
  const options = useMemo(() => buildUnorderedPairOptions(selectedPlayers), [selectedPlayers]);
  const [selectedKey, setSelectedKey] = useState('');
  const reconciledKey = useMemo(
    () => reconcilePairOption(options, selectedKey),
    [options, selectedKey],
  );
  const option = options.find((candidate) => candidate.key === reconciledKey) || null;
  const request = useMemo(() => buildPairFitV2Request(option), [option]);
  const [requestState, dispatch] = useReducer(pairFitRequestReducer, initialPairFitRequestState);
  const requestOk = request.ok;
  const requestKey = request.requestKey;
  const requestUrl = request.url;
  const requestTargetSeason = request.params?.target_season;

  useEffect(() => {
    if (selectedKey !== reconciledKey) setSelectedKey(reconciledKey);
  }, [reconciledKey, selectedKey]);

  useEffect(() => {
    if (!requestOk) {
      dispatch({ type: 'reset' });
      return undefined;
    }

    const controller = new AbortController();
    let alive = true;
    dispatch({ type: 'begin', requestKey });

    api.get(requestUrl, {
      params: { target_season: requestTargetSeason },
      signal: controller.signal,
    })
      .then((response) => {
        if (!alive) return;
        const data = validatePairFitV2Payload(response.data);
        dispatch({ type: 'resolve', requestKey, data });
      })
      .catch((error) => {
        if (!alive || error?.code === 'ERR_CANCELED') return;
        if (error instanceof Error && error.message.includes('malformed')) {
          dispatch({ type: 'fail', requestKey, error: error.message });
          return;
        }
        const responseData = error?.response?.data;
        try {
          if (responseData?.supported !== false) throw error;
          const refusal = validatePairFitV2Payload(responseData);
          dispatch({ type: 'resolve', requestKey, data: refusal });
        } catch (validationError) {
          const message = validationError?.message?.includes('malformed')
            ? validationError.message
            : apiErrorMessage(error, 'Pair Fit v2 is temporarily unavailable.');
          dispatch({ type: 'fail', requestKey, error: message });
        }
      });

    return () => {
      alive = false;
      controller.abort();
    };
  }, [requestKey, requestOk, requestTargetSeason, requestUrl]);

  if (validCards.length < 2) return null;

  const currentState = requestOk && requestState.requestKey === requestKey
    ? requestState
    : initialPairFitRequestState;
  const result = currentState.data;
  const playerNames = option?.cards.map((card) => card.playerName).join(' + ') || '';

  return (
    <section className="pair-fit-summary card shadow-sm mb-3" aria-labelledby="pair-fit-v2-title">
      <div className="card-body py-3">
        <div className="d-flex flex-column flex-lg-row justify-content-between gap-3">
          <div className="pair-fit-summary__intro">
            <h2 id="pair-fit-v2-title" className="h5 mb-1">Pair Fit v2</h2>
            {playerNames && <div className="fw-semibold">{playerNames}</div>}
          </div>

          {validCards.length > 2 && options.length > 0 && (
            <div className="pair-fit-summary__selector">
              <label className="form-label small fw-semibold mb-1" htmlFor="pair-fit-v2-pair">
                Pair to project
              </label>
              <select
                id="pair-fit-v2-pair"
                className="form-select form-select-sm"
                value={reconciledKey}
                onChange={(event) => setSelectedKey(event.target.value)}
              >
                {options.map((candidate) => (
                  <option key={candidate.key} value={candidate.key}>{candidate.label}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        {options.length === 0 && (
          <div className="alert alert-warning py-2 mt-3 mb-0" role="status">
            Pair Fit v2 requires two different selected players.
          </div>
        )}

        {options.length > 0 && !request.ok && (
          <div className="alert alert-warning py-2 mt-3 mb-0" role="status">
            {request.message}
          </div>
        )}

        {request.ok && currentState.status === 'loading' && (
          <div className="text-muted mt-3" role="status" aria-live="polite">
            Loading Pair Fit v2 projection...
          </div>
        )}

        {request.ok && currentState.status === 'error' && (
          <div className="alert alert-warning py-2 mt-3 mb-0" role="alert">
            {currentState.error}
          </div>
        )}

        {request.ok && result?.supported === false && (
          <div className="alert alert-warning py-2 mt-3 mb-0" role="status">
            {result.message}
          </div>
        )}

        {request.ok && result?.supported === true && (
          <div className="pair-fit-summary__result mt-3" aria-live="polite">
            <div>
              <div className="small text-muted">Projected shared-court net rating</div>
              <div className="d-flex align-items-baseline gap-2 flex-wrap">
                <span className="pair-fit-summary__value">{result.display_value}</span>
                <span className="small">points per 100 possessions</span>
              </div>
            </div>
            <div className="pair-fit-summary__context">
              <div className="fw-semibold">
                Confidence: {result.confidence === 'standard' ? 'Standard' : 'Lower'}
              </div>
              {result.confidence === 'lower' && (
                <div className="small">One or both prior player profiles were unavailable.</div>
              )}
              <div className="small text-muted mt-1">
                Contextual projection <span aria-hidden="true">&bull;</span>{' '}
                Typical final-test error &asymp; {result.typical_final_test_error.toFixed(1)} points per 100 possessions
              </div>
            </div>
          </div>
        )}

        <details className="pair-fit-summary__details mt-2">
          <summary>About this projection</summary>
          <p className="small text-muted mb-0 mt-2">
            This projects shared-court team net rating, not a chemistry score. Confidence reflects
            whether prior player profiles were available; it is not a probability. Results are
            contextual and have substantial uncertainty.
          </p>
        </details>
      </div>
    </section>
  );
}
