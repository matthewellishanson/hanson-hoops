# backend/app/api/endpoints/rookies.py
from fastapi import APIRouter
from app.services.rookies import get_rookie_height_stream

router = APIRouter(prefix="/rookies", tags=["Rookies"])

@router.get("/height-stream")
def rookie_height_stream(start: int = 2000, end: int = 2025):
    return get_rookie_height_stream(start, end)
