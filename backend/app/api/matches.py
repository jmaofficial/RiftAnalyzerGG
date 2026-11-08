from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.api.dependencies import get_riot_client, get_session
from app.clients.riot_client import RiotClient
from app.db.models import Match
from app.schemas.matches import MatchImportResult, MatchRead
from app.services.match_service import MatchService


router = APIRouter(prefix="/api/matches", tags=["Matches"])
SessionDep = Annotated[Session, Depends(get_session)]
RiotDep = Annotated[RiotClient, Depends(get_riot_client)]
MatchId = Annotated[str, Path(pattern=r"^[A-Z0-9]+_[0-9]+$", max_length=100)]


def require_match(session: Session, match_id: str) -> Match:
    match = MatchService(session).get_stored_match(match_id)
    if match is None:
        raise HTTPException(404, "Match not stored. Sync it first.")
    return match


@router.post("/{match_id}/sync", response_model=MatchImportResult)
def sync_match(
    match_id: MatchId, session: SessionDep, riot: RiotDep,
    include_timeline: bool = True,
):
    match, import_status = MatchService(session, riot).import_match(match_id, include_timeline)
    return MatchImportResult(
        match_id=match.match_id, status=import_status,
        timeline_available=match.timeline_data is not None,
    )


@router.get("/{match_id}", response_model=MatchRead)
def get_match(match_id: MatchId, session: SessionDep):
    return require_match(session, match_id)


@router.get("/{match_id}/raw")
def get_raw_match(match_id: MatchId, session: SessionDep) -> dict:
    """The full original Riot match payload, including teams, objectives and perks."""
    return require_match(session, match_id).raw_data


@router.get("/{match_id}/timeline")
def get_match_timeline(match_id: MatchId, session: SessionDep) -> dict:
    match = require_match(session, match_id)
    if match.timeline_data is None:
        raise HTTPException(404, "Timeline not stored. Sync with include_timeline=true.")
    return match.timeline_data
