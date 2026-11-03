from fastapi import APIRouter

from app.clients.riot_client import RiotClient
from app.core.config import RIOT_API_KEY


router = APIRouter(prefix="/api/players", tags=["Players"])


@router.get("/{game_name}/{tag_line}")
def get_player(game_name: str, tag_line: str):

    with RiotClient(RIOT_API_KEY) as riot:
        return riot.get_account_by_riot_id(game_name, tag_line)