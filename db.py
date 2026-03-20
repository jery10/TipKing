"""
Supabase database client for TipKing.
"""
import os
from supabase import create_client, Client
import pandas as pd

def _get_secret(key):
    try:
        import streamlit as st
        return st.secrets.get(key, os.getenv(key, ""))
    except Exception:
        return os.getenv(key, "")

_sb: Client = None

def get_db() -> Client:
    global _sb
    if _sb is None:
        url = _get_secret("SUPABASE_URL")
        key = _get_secret("SUPABASE_KEY")
        _sb = create_client(url, key)
    return _sb


def submit_tip(handle: str, competition: str, home_team: str, away_team: str,
               match_date: str, result_pick: str, home_goals: int, away_goals: int,
               confidence: int, reasoning: str) -> bool:
    try:
        db = get_db()
        db.table("tips").insert({
            "handle": handle.lstrip("@").lower(),
            "competition": competition,
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "result_pick": result_pick,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "confidence": confidence,
            "reasoning": reasoning,
        }).execute()
        return True
    except Exception as e:
        print(f"submit_tip error: {e}")
        return False


def get_tips_for_match(home_team: str, away_team: str) -> pd.DataFrame:
    try:
        db = get_db()
        res = db.table("tips").select("*")\
            .eq("home_team", home_team).eq("away_team", away_team)\
            .order("submitted_at", desc=False).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def get_my_tips(handle: str) -> pd.DataFrame:
    try:
        db = get_db()
        res = db.table("tips").select("*")\
            .eq("handle", handle.lstrip("@").lower())\
            .order("submitted_at", desc=True).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def get_leaderboard() -> pd.DataFrame:
    try:
        db = get_db()
        res = db.table("tips").select("*").not_.is_("is_correct", "null").execute()
        if not res.data:
            return pd.DataFrame()
        df = pd.DataFrame(res.data)
        lb = df.groupby("handle").agg(
            Tips=("id", "count"),
            Correct=("is_correct", "sum"),
        ).reset_index()
        lb["Accuracy"] = (lb["Correct"] / lb["Tips"] * 100).round(1)
        lb = lb.sort_values(["Accuracy", "Correct"], ascending=False).reset_index(drop=True)
        lb.index += 1
        lb.columns = ["Twitter", "Tips", "Correct", "Accuracy %"]
        return lb
    except Exception:
        return pd.DataFrame()


def get_all_tips() -> pd.DataFrame:
    """Admin: all tips."""
    try:
        db = get_db()
        res = db.table("tips").select("*").order("submitted_at", desc=True).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def mark_result(tip_id: str, is_correct: bool, actual_home: int, actual_away: int):
    """Admin: mark a tip as correct/wrong after match."""
    try:
        db = get_db()
        db.table("tips").update({
            "is_correct": is_correct,
            "actual_home": actual_home,
            "actual_away": actual_away,
        }).eq("id", tip_id).execute()
        return True
    except Exception:
        return False


def has_already_tipped(handle: str, home_team: str, away_team: str) -> bool:
    try:
        db = get_db()
        res = db.table("tips").select("id")\
            .eq("handle", handle.lstrip("@").lower())\
            .eq("home_team", home_team).eq("away_team", away_team).execute()
        return len(res.data) > 0
    except Exception:
        return False
