from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Player
from app.clients.riot_client import RiotClient
from app.repositories.player_repository import PlayerRepository


class PlayerService:

    def __init__(self, riot_client: RiotClient, session: Session):
        self.riot_client = riot_client
        self.repository = PlayerRepository(session)
        self.session = session

    def get_or_create_player(self, game_name: str, tag_line: str) -> Player:

        # Fetch player data from Riot API
        player_data = self.riot_client.get_account_by_riot_id(
            game_name, tag_line
        )

        # Check if player exists in database
        player = self.repository.get_by_puuid(player_data["puuid"])

        if player is None:
            # Create new player
            player = Player(
                puuid=player_data["puuid"],
                game_name=player_data["gameName"],
                tag_line=player_data["tagLine"]
            )
            self.repository.create(player)

        else:
            # Update existing player
            player.game_name = player_data["gameName"]
            player.tag_line = player_data["tagLine"]

        player.last_updated = datetime.now(timezone.utc)
        self.session.commit()

        return player

    def get_player_matches(self, game_name: str, tag_line: str) -> list[str]:
        player = self.get_or_create_player(game_name, tag_line)
        return self.riot_client.get_match_history_by_puuid(player.puuid, count=10)
