"""
Generates docs/data.json: the full season's history of zero-point starters,
recomputed fresh from ESPN on every run.
"""

import os
import json
from datetime import datetime, timezone
from espn_api.football import League

LEAGUE_ID = int(os.environ["ESPN_LEAGUE_ID"])
YEAR = int(os.environ.get("ESPN_YEAR", 2026))
ESPN_S2 = os.environ.get("ESPN_S2") or None
ESPN_SWID = os.environ.get("ESPN_SWID") or None

NON_STARTING_SLOTS = {"BE", "IR", "IR+"}

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data.json")


def get_league() -> League:
    kwargs = {"league_id": LEAGUE_ID, "year": YEAR}
    if ESPN_S2 and ESPN_SWID:
        kwargs["espn_s2"] = ESPN_S2
        kwargs["swid"] = ESPN_SWID
    return League(**kwargs)


def collect_entries(league: League):
    entries = []
    last_completed_week = max(league.current_week - 1, 0)

    for week in range(1, last_completed_week + 1):
        try:
            box_scores = league.box_scores(week=week)
        except Exception as e:
            print(f"Skipping week {week}: {e}")
            continue

        for matchup in box_scores:
            pairs = [
                (matchup.home_team, matchup.home_lineup),
                (matchup.away_team, matchup.away_lineup),
            ]
            for team, lineup in pairs:
                if team is None or lineup is None:
                    continue
                for player in lineup:
                    if player.slot_position in NON_STARTING_SLOTS:
                        continue
                    game_played = getattr(player, "game_played", 100)
                    if game_played == 100 and player.points == 0:
                        entry_id = f"{team.team_id}_{week}_{getattr(player, 'playerId', player.name)}_{player.slot_position}"
                        entries.append({
                            "id": entry_id,
                            "team": team.team_name,
                            "week": week,
                            "player": player.name,
                            "slot": player.slot_position,
                        })
    return entries


def main():
    league = get_league()
    teams = [t.team_name for t in league.teams]
    entries = collect_entries(league)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "league_id": LEAGUE_ID,
        "year": YEAR,
        "current_week": league.current_week,
        "teams": teams,
        "entries": entries,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {len(entries)} entries for {len(teams)} teams to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
