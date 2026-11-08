from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.db.models import Player


class PlayerRepository:

    def __init__(self, session: Session):
        self.session = session

    def get_by_puuid(self, puuid: str) -> Player | None:
        return self.session.get(Player, puuid)

    def get_by_riot_id(self, game_name: str, tag_line: str) -> Player | None:
        return self.session.scalar(select(Player).where(
            func.lower(Player.game_name) == game_name.lower(),
            func.lower(Player.tag_line) == tag_line.lower(),
        ))

    def create(self, player: Player) -> Player:
        self.session.add(player)
        self.session.flush()
        return player
