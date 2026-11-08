from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.schemas.analysis import AnalysisOptions, AnalysisReport, FeatureDataset, Position
from app.services.analysis_service import AnalysisService
from app.services.match_service import StoredPlayerNotFound


router = APIRouter(prefix="/api/players", tags=["Analysis"])
SessionDep = Annotated[Session, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=500)]
Patch = Annotated[str | None, Query(pattern=r"^\d+\.\d+$", max_length=20)]
Champion = Annotated[int | None, Query(ge=1)]


@router.get("/{game_name}/{tag_line}/analysis/features", response_model=FeatureDataset)
def get_analysis_features(
    game_name: str, tag_line: str, session: SessionDep,
    limit: Limit = 200, position: Position | None = None, patch: Patch = None,
    champion_id: Champion = None,
):
    """Compute checkpoints, phases, sidelane proxies and post-event windows from stored games."""
    try:
        return AnalysisService(session).features(game_name, tag_line, limit, position, patch, champion_id)
    except StoredPlayerNotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/{game_name}/{tag_line}/analysis", response_model=AnalysisReport)
def get_analysis_report(
    game_name: str, tag_line: str, session: SessionDep,
    limit: Limit = 200, position: Position | None = None, patch: Patch = None,
    champion_id: Champion = None,
):
    """Exploratory associations with evidence. Insufficient data is a normal 200 response."""
    try:
        return AnalysisService(session).report(game_name, tag_line, limit, position, patch, champion_id)
    except StoredPlayerNotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/{game_name}/{tag_line}/analysis/options", response_model=AnalysisOptions)
def get_analysis_options(game_name: str, tag_line: str, session: SessionDep):
    """Champion and lane choices from all stored solo/duo games, without Riot requests."""
    try:
        return AnalysisService(session).options(game_name, tag_line)
    except StoredPlayerNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
