"""Versioned Pair Fit v2 HTTP adapter."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.pair_fit_v2_service import get_pair_fit_predictor


router = APIRouter(prefix="/fit/v2", tags=["Pair Fit v2"])

UNITS = "points per 100 possessions"


class PairFitV2SupportedResponse(BaseModel):
    supported: Literal[True]
    model_name: str
    model_version: str
    output_definition: str
    units: str
    player_a_id: str
    player_b_id: str
    target_season: str
    projected_net_rating: float
    display_value: str
    confidence: Literal["standard", "lower"]
    confidence_meaning: str
    player_a_profile_season: str | None
    player_b_profile_season: str | None
    player_a_history_missing: bool
    player_b_history_missing: bool
    typical_final_test_error: float
    error_disclosure: str


class PairFitV2RefusalResponse(BaseModel):
    supported: Literal[False]
    model_name: str
    model_version: str
    player_a_id: str
    player_b_id: str
    target_season: str
    reason_code: str
    message: str


def _refusal_status(reason_code: str) -> int:
    return 400 if reason_code == "same_player" else 422


@router.get(
    "/pair/{player_a_id}/{player_b_id}",
    response_model=PairFitV2SupportedResponse,
    responses={
        400: {"model": PairFitV2RefusalResponse, "description": "Identical-player refusal"},
        422: {"model": PairFitV2RefusalResponse, "description": "Invalid or unsupported input"},
    },
)
def pair_fit_v2(
    player_a_id: str,
    player_b_id: str,
    target_season: str = Query(...),
):
    predictor = get_pair_fit_predictor()
    result = predictor.predict_pair_fit(player_a_id, player_b_id, target_season)
    model = predictor.model

    if not result.get("supported"):
        refusal = (result.get("refusal_reasons") or [{}])[0]
        reason_code = str(refusal.get("code") or "unsupported_request")
        message = str(refusal.get("message") or "This Pair Fit request is unsupported.")
        return JSONResponse(
            status_code=_refusal_status(reason_code),
            content={
                "supported": False,
                "model_name": model["model_name"],
                "model_version": result["model_version"],
                "player_a_id": player_a_id,
                "player_b_id": player_b_id,
                "target_season": target_season,
                "reason_code": reason_code,
                "message": message,
            },
        )

    player_a_id_normalized = str(int(player_a_id))
    player_b_id_normalized = str(int(player_b_id))
    history = result["history"]["players"]
    final_test = model["final_test"]
    return {
        "supported": True,
        "model_name": model["model_name"],
        "model_version": result["model_version"],
        "output_definition": model["output_definition"],
        "units": UNITS,
        "player_a_id": player_a_id_normalized,
        "player_b_id": player_b_id_normalized,
        "target_season": result["target_season"],
        "projected_net_rating": result["prediction_full_precision"],
        "display_value": result["prediction_display"],
        "confidence": result["confidence"],
        "confidence_meaning": model["confidence"]["meaning"],
        "player_a_profile_season": history[player_a_id_normalized]["selected_profile_season"],
        "player_b_profile_season": history[player_b_id_normalized]["selected_profile_season"],
        "player_a_history_missing": history[player_a_id_normalized]["missing"],
        "player_b_history_missing": history[player_b_id_normalized]["missing"],
        "typical_final_test_error": final_test["mae"],
        "error_disclosure": final_test["public_disclosure"],
    }
