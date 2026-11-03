import os
from dotenv import load_dotenv

from app.clients.riot_client import RiotClient

load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")

with RiotClient(API_KEY) as riot:

    # 1. Get account
    account = riot.get_account_by_riot_id("jonnybravo", "1998")
    puuid = account["puuid"]

    print(f"Player: {account['gameName']}#{account['tagLine']}")

    # 2. Get match history
    match_ids = riot.get_match_history_by_puuid(puuid, count=20)

    print(f"Found {len(match_ids)} matches")

    # 3. Get match details
    for match_id in match_ids:
        match = riot.get_match_details_by_match_id(match_id)

        for participant in match["info"]["participants"]:
            if participant["puuid"] == puuid:
                print(
                    f"{participant['championName']}: "
                    f"{participant['kills']}/"
                    f"{participant['deaths']}/"
                    f"{participant['assists']} "
                    f"| Win: {participant['win']}"
                )
                break