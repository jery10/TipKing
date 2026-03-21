import os
import time
import requests
from datetime import datetime, timedelta, timezone

_cache = {"data": None, "ts": 0}
_CACHE_TTL = 300  # 5 minutes

COMPETITIONS = {
    "PL":  {"name": "Premier League",   "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "country": "England"},
    "PD":  {"name": "La Liga",          "flag": "🇪🇸", "country": "Spain"},
    "CL":  {"name": "Champions League", "flag": "🏆", "country": "Europe"},
    "BL1": {"name": "Bundesliga",       "flag": "🇩🇪", "country": "Germany"},
    "SA":  {"name": "Serie A",          "flag": "🇮🇹", "country": "Italy"},
    "FL1": {"name": "Ligue 1",          "flag": "🇫🇷", "country": "France"},
}

def _api_key():
    return os.getenv("FOOTBALL_DATA_API_KEY", "")

def get_upcoming(days=14):
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < _CACHE_TTL:
        cutoff = datetime.now() + timedelta(days=days)
        return [m for m in _cache["data"] if m["date"] <= cutoff]

    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    all_matches = []
    for comp_code in COMPETITIONS:
        try:
            resp = requests.get(
                f"https://api.football-data.org/v4/competitions/{comp_code}/matches",
                headers={"X-Auth-Token": _api_key()},
                params={"dateFrom": today, "dateTo": future},
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            for m in resp.json().get("matches", []):
                if m.get("status") in ("FINISHED","IN_PLAY","PAUSED","CANCELLED","POSTPONED"):
                    continue
                dt = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).replace(tzinfo=None)
                all_matches.append({
                    "match_id":   m["id"],
                    "competition": comp_code,
                    "comp_name":  COMPETITIONS[comp_code]["name"],
                    "comp_flag":  COMPETITIONS[comp_code]["flag"],
                    "date":       dt,
                    "date_str":   dt.strftime("%a %d %b · %H:%M"),
                    "date_only":  str(dt.date()),
                    "home_team":  m["homeTeam"]["name"],
                    "away_team":  m["awayTeam"]["name"],
                })
        except Exception as e:
            print(f"fixtures {comp_code}: {e}")

    if not all_matches:
        return []
    sorted_matches = sorted(all_matches, key=lambda x: x["date"])
    _cache["data"] = sorted_matches
    _cache["ts"] = time.time()
    cutoff = datetime.now() + timedelta(days=days)
    return [m for m in sorted_matches if m["date"] <= cutoff]
