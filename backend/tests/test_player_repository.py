from app.db.database import SessionLocal
from app.db.models import Player
from app.repositories.player_repository import PlayerRepository


with SessionLocal() as session:
    repository = PlayerRepository(session)

    player = Player(
        puuid="test-puuid-123",
        game_name="TestPlayer",
        tag_line="EUW"
    )

    existing = repository.get_by_puuid(player.puuid)

    if existing is None:
        repository.create(player)
        session.commit()
        print("Player created!")
    else:
        print("Player already exists!")

    saved_player = repository.get_by_puuid(player.puuid)
    print(saved_player.game_name, saved_player.tag_line)