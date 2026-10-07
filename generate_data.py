"""
Generates docs/data.json: the full season's history of zero-point starters
(plus near-misses, team logos and owners), recomputed fresh from ESPN on every run.
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

# Starters who scored within this many points of zero (either direction,
# excluding exactly 0, which counts as a full zero instead) count as a
# "close call" -- e.g. 3 means anything from -3 to 3 excluding 0.
CLOSE_CALL_RANGE = 3

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "data.json")


def get_league() -> League:
    kwargs = {"league_id": LEAGUE_ID, "year": YEAR}
    if ESPN_S2 and ESPN_SWID:
        kwargs["espn_s2"] = ESPN_S2
        kwargs["swid"] = ESPN_SWID
    return League(**kwargs)


def owner_info(team):
    """Return (display names, ESPN usernames) for a team's owners.
    Display name is "First Last" when ESPN has it, else the username."""
    names, usernames = [], []
    for owner in getattr(team, "owners", None) or []:
        if not isinstance(owner, dict):
            continue
        full = " ".join(
            p.strip() for p in (owner.get("firstName"), owner.get("lastName")) if p and p.strip()
        )
        username = (owner.get("displayName") or "").strip()
        if full or username:
            names.append(full or username)
        if username:
            usernames.append(username)
    return names, usernames


def collect_entries(league: League):
    """Recompute every completed week from scratch. Idempotent by design --
    each run fully replaces data.json rather than appending, so there's no
    risk of duplicate or stale entries. Returns (zeros, close_calls)."""
    zeros = []
    close_calls = []
    last_week = min(league.current_week, 18)

    for week in range(1, last_week + 1):
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
                    if game_played != 100:
                        continue

                    if player.points == 0:
                        entry_id = f"{team.team_id}_{week}_{getattr(player, 'playerId', player.name)}_{player.slot_position}"
                        zeros.append({
                            "id": entry_id,
                            "team_id": team.team_id,
                            "team": team.team_name,
                            "week": week,
                            "player": player.name,
                            "slot": player.slot_position,
                        })
                    elif player.points != 0 and abs(player.points) <= CLOSE_CALL_RANGE:
                        close_calls.append({
                            "team_id": team.team_id,
                            "team": team.team_name,
                            "week": week,
                            "player": player.name,
                            "slot": player.slot_position,
                            "points": round(player.points, 1),
                        })
    return zeros, close_calls


def main():
    league = get_league()
    teams = []
    for t in league.teams:
        names, usernames = owner_info(t)
        teams.append({
            "id": t.team_id,
            "name": t.team_name,
            "logo": getattr(t, "logo_url", None) or None,
            "owners": names,
            "owner_usernames": usernames,
        })
    entries, close_calls = collect_entries(league)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "league_id": LEAGUE_ID,
        "year": YEAR,
        "current_week": league.current_week,
        "teams": teams,
        "entries": entries,
        "close_calls": close_calls,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {len(entries)} zeros and {len(close_calls)} close calls for {len(teams)} teams to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
