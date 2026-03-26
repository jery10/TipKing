"""
Auto-settlement: fetches finished match scores from football-data.org
and settles any pending tips. Called on a background thread every 30 min.
"""
import os
import time
import threading
import requests
from datetime import datetime, timedelta
from fixtures import COMPETITIONS

_last_run = {"ts": 0, "settled": 0, "log": []}


def _api_key():
    return os.getenv("FOOTBALL_DATA_API_KEY", "")


def _fuzzy(a, b):
    a, b = a.lower().strip(), b.lower().strip()
    return a == b or a in b or b in a or \
        a.replace(" fc", "") == b.replace(" fc", "") or \
        a.replace(" cf", "") == b.replace(" cf", "")


def fetch_finished():
    """Fetch FINISHED matches from the last 30 days across all competitions."""
    date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    date_to   = datetime.now().strftime("%Y-%m-%d")
    finished  = []

    for comp_code in COMPETITIONS:
        try:
            resp = requests.get(
                f"https://api.football-data.org/v4/competitions/{comp_code}/matches",
                headers={"X-Auth-Token": _api_key()},
                params={"status": "FINISHED", "dateFrom": date_from, "dateTo": date_to},
                timeout=12,
            )
            if resp.status_code == 429:
                print(f"settler {comp_code}: rate limited")
                time.sleep(60)
                continue
            if resp.status_code != 200:
                continue
            for m in resp.json().get("matches", []):
                ft = m.get("score", {}).get("fullTime", {})
                hg, ag = ft.get("home"), ft.get("away")
                if hg is None or ag is None:
                    continue
                finished.append({
                    "comp":       comp_code,
                    "home":       m["homeTeam"]["name"],
                    "away":       m["awayTeam"]["name"],
                    "home_goals": int(hg),
                    "away_goals": int(ag),
                })
        except Exception as e:
            print(f"settler fetch {comp_code}: {e}")

    return finished


def auto_settle():
    """Main settle loop. Returns number of tips settled."""
    import db

    pending_matches = db.get_pending_matches()
    if not pending_matches:
        return 0

    finished = fetch_finished()
    if not finished:
        return 0

    total = 0
    log   = []
    for match in pending_matches:
        home = match["home_team"]
        away = match["away_team"]
        for f in finished:
            if _fuzzy(home, f["home"]) and _fuzzy(away, f["away"]):
                n = db.settle_match(home, away, f["home_goals"], f["away_goals"])
                if n:
                    msg = f"{home} vs {away} → {f['home_goals']}-{f['away_goals']} ({n} tips)"
                    print(f"auto_settle: {msg}")
                    log.append(msg)
                    total += n
                break

    _last_run["ts"]      = time.time()
    _last_run["settled"] = total
    _last_run["log"]     = log
    return total


def start_background():
    """Launch a daemon thread that auto-settles every 30 minutes."""
    def loop():
        # Wait 60s after startup before first run
        time.sleep(60)
        while True:
            try:
                auto_settle()
            except Exception as e:
                print(f"auto_settle error: {e}")
            time.sleep(1800)  # 30 minutes

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("settler: background thread started")
