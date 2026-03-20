import os
from supabase import create_client, Client

_sb: Client = None

def get_db() -> Client:
    global _sb
    if _sb is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        _sb = create_client(url, key)
    return _sb


def submit_tip(handle, competition, home_team, away_team,
               match_date, result_pick, home_goals, away_goals,
               confidence, reasoning):
    try:
        get_db().table("tips").insert({
            "handle": handle.lstrip("@").lower().strip(),
            "competition": competition,
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "result_pick": result_pick,
            "home_goals": int(home_goals),
            "away_goals": int(away_goals),
            "confidence": int(confidence),
            "reasoning": reasoning,
        }).execute()
        return True
    except Exception as e:
        print(f"submit_tip error: {e}")
        return False


def get_tips_for_match(home_team, away_team):
    try:
        res = get_db().table("tips").select("*")\
            .eq("home_team", home_team).eq("away_team", away_team)\
            .order("submitted_at").execute()
        return res.data or []
    except Exception:
        return []


def has_tipped(handle, home_team, away_team):
    try:
        res = get_db().table("tips").select("id")\
            .eq("handle", handle.lstrip("@").lower().strip())\
            .eq("home_team", home_team).eq("away_team", away_team).execute()
        return len(res.data) > 0
    except Exception:
        return False


def get_my_tips(handle):
    try:
        res = get_db().table("tips").select("*")\
            .eq("handle", handle.lstrip("@").lower().strip())\
            .order("submitted_at", desc=True).execute()
        return res.data or []
    except Exception:
        return []


def get_leaderboard():
    try:
        res = get_db().table("tips").select("*")\
            .not_.is_("is_correct", "null").execute()
        if not res.data:
            return []
        # Aggregate by handle
        agg = {}
        for t in res.data:
            h = t["handle"]
            if h not in agg:
                agg[h] = {"handle": h, "tips": 0, "correct": 0}
            agg[h]["tips"] += 1
            if t["is_correct"]:
                agg[h]["correct"] += 1
        lb = [v for v in agg.values() if v["tips"] >= 3]
        for row in lb:
            row["accuracy"] = round(row["correct"] / row["tips"] * 100, 1)
        lb.sort(key=lambda x: (-x["accuracy"], -x["correct"]))
        return lb
    except Exception:
        return []


def get_all_tips():
    try:
        res = get_db().table("tips").select("*")\
            .order("submitted_at", desc=True).execute()
        return res.data or []
    except Exception:
        return []


def get_recent_winners(limit=5):
    try:
        res = get_db().table("tips").select("*")\
            .eq("is_correct", True)\
            .order("submitted_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception:
        return []


def get_stats():
    try:
        all_tips = get_db().table("tips").select("*").execute().data or []
        if not all_tips:
            return {"total": 0, "tipsters": 0, "settled": 0, "correct": 0}
        return {
            "total": len(all_tips),
            "tipsters": len(set(t["handle"] for t in all_tips)),
            "settled": sum(1 for t in all_tips if t["is_correct"] is not None),
            "correct": sum(1 for t in all_tips if t["is_correct"] is True),
        }
    except Exception:
        return {"total": 0, "tipsters": 0, "settled": 0, "correct": 0}


def mark_result(tip_id, is_correct, actual_home, actual_away):
    try:
        get_db().table("tips").update({
            "is_correct": is_correct,
            "actual_home": actual_home,
            "actual_away": actual_away,
        }).eq("id", tip_id).execute()
        return True
    except Exception:
        return False
