"""Fetch upcoming fixtures from football-data.org (shared with betpredict)."""
import os
import requests
import pandas as pd

COMPETITIONS = {
    "PL": {"name": "Premier League", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "PD": {"name": "La Liga", "flag": "🇪🇸"},
    "CL": {"name": "Champions League", "flag": "🏆"},
    "BL1": {"name": "Bundesliga", "flag": "🇩🇪"},
    "SA":  {"name": "Serie A", "flag": "🇮🇹"},
}

def _api_key():
    try:
        import streamlit as st
        return st.secrets.get("FOOTBALL_DATA_API_KEY", os.getenv("FOOTBALL_DATA_API_KEY", ""))
    except Exception:
        return os.getenv("FOOTBALL_DATA_API_KEY", "")

def get_upcoming(competition: str = "PL", days: int = 7) -> pd.DataFrame:
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    future = (pd.Timestamp.now() + pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        resp = requests.get(
            f"https://api.football-data.org/v4/competitions/{competition}/matches",
            headers={"X-Auth-Token": _api_key()},
            params={"dateFrom": today, "dateTo": future},
            timeout=10,
        )
        resp.raise_for_status()
        matches = []
        for m in resp.json().get("matches", []):
            if m.get("status") in ("FINISHED", "IN_PLAY", "PAUSED", "CANCELLED", "POSTPONED"):
                continue
            matches.append({
                "match_id": m["id"],
                "competition": competition,
                "comp_name": COMPETITIONS.get(competition, {}).get("name", competition),
                "date": pd.to_datetime(m["utcDate"]).tz_localize(None),
                "home_team": m["homeTeam"]["name"],
                "away_team": m["awayTeam"]["name"],
            })
        df = pd.DataFrame(matches)
        if not df.empty:
            df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"fixtures error: {e}")
        return pd.DataFrame()
