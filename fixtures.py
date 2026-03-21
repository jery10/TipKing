import os
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

_CACHE_TTL  = 3600        # 1 hour in-memory
_FILE_CACHE = "/tmp/fixtures_cache.json"
_mem = {"data": None, "ts": 0}

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


def _load_file_cache():
    """Load from /tmp file cache — survives process restarts within a deployment."""
    try:
        with open(_FILE_CACHE) as f:
            saved = json.load(f)
        matches = []
        for m in saved.get("data", []):
            m["date"] = datetime.fromisoformat(m["date"])
            matches.append(m)
        return matches, saved.get("ts", 0)
    except Exception:
        return None, 0


def _save_file_cache(matches):
    try:
        serialisable = []
        for m in matches:
            row = dict(m)
            row["date"] = m["date"].isoformat()
            serialisable.append(row)
        with open(_FILE_CACHE, "w") as f:
            json.dump({"data": serialisable, "ts": time.time()}, f)
    except Exception as e:
        print(f"fixtures cache write error: {e}")


def _fetch_all():
    today  = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    def fetch_comp(comp_code):
        try:
            resp = requests.get(
                f"https://api.football-data.org/v4/competitions/{comp_code}/matches",
                headers={"X-Auth-Token": _api_key()},
                params={"dateFrom": today, "dateTo": future},
                timeout=12,
            )
            if resp.status_code == 429:
                print(f"fixtures {comp_code}: rate limited")
                return []
            if resp.status_code != 200:
                print(f"fixtures {comp_code}: HTTP {resp.status_code}")
                return []
            matches = []
            for m in resp.json().get("matches", []):
                if m.get("status") in ("FINISHED", "IN_PLAY", "PAUSED", "CANCELLED", "POSTPONED"):
                    continue
                dt = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).replace(tzinfo=None)
                matches.append({
                    "match_id":    m["id"],
                    "competition": comp_code,
                    "comp_name":   COMPETITIONS[comp_code]["name"],
                    "comp_flag":   COMPETITIONS[comp_code]["flag"],
                    "date":        dt,
                    "date_str":    dt.strftime("%a %d %b · %H:%M"),
                    "date_only":   str(dt.date()),
                    "home_team":   m["homeTeam"]["name"],
                    "away_team":   m["awayTeam"]["name"],
                })
            return matches
        except Exception as e:
            print(f"fixtures {comp_code}: {e}")
            return []

    all_matches = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_comp, code): code for code in COMPETITIONS}
        for future in as_completed(futures):
            all_matches.extend(future.result())

    return sorted(all_matches, key=lambda x: x["date"]) if all_matches else []


def get_upcoming(days=14):
    now = time.time()
    cutoff = datetime.now() + timedelta(days=days)

    # 1. Serve from in-memory cache if fresh
    if _mem["data"] is not None and now - _mem["ts"] < _CACHE_TTL:
        return [m for m in _mem["data"] if m["date"] <= cutoff]

    # 2. Try file cache — warm memory and serve if still fresh enough (< 2h)
    file_data, file_ts = _load_file_cache()
    if file_data and now - file_ts < _CACHE_TTL * 2:
        _mem["data"] = file_data
        _mem["ts"]   = file_ts
        return [m for m in file_data if m["date"] <= cutoff]

    # 3. Fetch from API
    fresh = _fetch_all()
    if fresh:
        _mem["data"] = fresh
        _mem["ts"]   = now
        _save_file_cache(fresh)
        return [m for m in fresh if m["date"] <= cutoff]

    # 4. API failed — serve stale data rather than an empty page
    stale = file_data or _mem["data"]
    if stale:
        print("fixtures: API failed, serving stale cache")
        return [m for m in stale if m["date"] <= cutoff]

    return []
