import csv
import io
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_riot_client, get_session
from app.clients.riot_client import RiotClient
from app.services.player_service import PlayerService
from app.schemas.matches import MatchPage, MatchSample, SyncResult
from app.services.match_service import MatchService, StoredPlayerNotFound


router = APIRouter(prefix="/api/players", tags=["Players"])
SessionDep = Annotated[Session, Depends(get_session)]
RiotDep = Annotated[RiotClient, Depends(get_riot_client)]
Start = Annotated[int, Query(ge=0)]
PageCount = Annotated[int, Query(ge=1, le=1000)]
Queue = Annotated[int | None, Query(ge=0)]


@router.get("/{game_name}/{tag_line}")
def get_player(game_name: str, tag_line: str, session: SessionDep, riot: RiotDep):
    player = PlayerService(riot, session).get_or_create_player(game_name, tag_line)
    return {
        "puuid": player.puuid,
        "game_name": player.game_name,
        "tag_line": player.tag_line,
    }


@router.get("/{game_name}/{tag_line}/matches", response_model=list[str])
def get_player_matches(game_name: str, tag_line: str, session: SessionDep, riot: RiotDep):
    return PlayerService(riot, session).get_player_matches(game_name, tag_line)


@router.post("/{game_name}/{tag_line}/matches/sync", response_model=SyncResult)
def sync_player_matches(
    game_name: str, tag_line: str, session: SessionDep, riot: RiotDep,
    start: Start = 0, count: Annotated[int, Query(ge=1, le=100)] = 10,
    queue: Queue = None, include_timeline: bool = True,
):
    """Import one Riot history page. Check completed and next_start before continuing."""
    return MatchService(session, riot).sync_player_matches(
        game_name, tag_line, start, count, queue, include_timeline
    )


def stored_match_page(
    session: Session, game_name: str, tag_line: str,
    start: int, count: int, queue: int | None,
) -> MatchPage:
    try:
        return MatchService(session).get_stored_matches(game_name, tag_line, start, count, queue)
    except StoredPlayerNotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/{game_name}/{tag_line}/matches/stored", response_model=MatchPage)
def get_stored_matches(
    game_name: str, tag_line: str, session: SessionDep,
    start: Start = 0, count: PageCount = 100, queue: Queue = None,
):
    """Read a flat dataset from PostgreSQL only; no Riot calls."""
    return stored_match_page(session, game_name, tag_line, start, count, queue)


@router.get("/{game_name}/{tag_line}/matches/export")
def export_matches(
    game_name: str, tag_line: str, session: SessionDep,
    start: Start = 0, count: PageCount = 1000, queue: Queue = None,
):
    """Export one page of the same flat dataset as CSV."""
    page = stored_match_page(session, game_name, tag_line, start, count, queue)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(MatchSample.model_fields))
    writer.writeheader()
    for sample in page.items:
        row = sample.model_dump(mode="json")
        for key, value in row.items():
            if isinstance(value, list):
                row[key] = json.dumps(value)
            elif isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                row[key] = "'" + value
        writer.writerow(row)
    return Response(
        content=buffer.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="matches.csv"'},
    )
