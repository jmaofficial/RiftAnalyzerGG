from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.clients.riot_client import RiotClient
from app.core.config import RIOT_API_KEY
from app.db.database import SessionLocal


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def get_riot_client() -> Iterator[RiotClient]:
    with RiotClient(RIOT_API_KEY) as riot:
        yield riot
