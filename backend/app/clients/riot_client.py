import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")


import httpx
from urllib.parse import quote


class RiotClient:
    BASE_URL = "https://europe.api.riotgames.com"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Riot API key is required.")

        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={"X-Riot-Token": api_key},
            timeout=10.0
        )

    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Send a GET request to the Riot API."""

        response = self.client.get(endpoint, params=params)
        response.raise_for_status()

        return response.json()

    def get_account_by_riot_id(
        self,
        game_name: str,
        tag_line: str
    ) -> dict:
        """Retrieve account information using a Riot ID."""

        game_name = quote(game_name, safe="")
        tag_line = quote(tag_line, safe="")

        endpoint = (
            f"/riot/account/v1/accounts/by-riot-id/"
            f"{game_name}/{tag_line}"
        )

        return self._get(endpoint)

    def get_match_history_by_puuid(
        self,
        puuid: str,
        start: int = 0,
        count: int = 20
    ) -> list[str]:
        """Retrieve match IDs for a player."""

        endpoint = f"/lol/match/v5/matches/by-puuid/{puuid}/ids"

        params = {
            "start": start,
            "count": count
        }

        return self._get(endpoint, params=params)

    def get_match_details_by_match_id(
        self,
        match_id: str
    ) -> dict:
        """Retrieve detailed information about a match."""

        endpoint = f"/lol/match/v5/matches/{match_id}"

        return self._get(endpoint)

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

