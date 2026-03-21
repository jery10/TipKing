import os
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

_sb: Client = None

def get_db() -> Client:
    global _sb
    if _sb is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        _sb = create_client(url, key)
    return _sb


def register_user(email, password, username, twitter="", instagram="", tiktok=""):
    try:
        email = email.lower().strip()
        username = username.lower().strip()
        existing_email = get_db().table("users").select("id").eq("email", email).execute()
        if existing_email.data:
            return False, "An account with that email already exists."
        existing_user = get_db().table("users").select("id").eq("username", username).execute()
        if existing_user.data:
            return False, "That username is already taken."
        get_db().table("users").insert({
            "email":     email,
            "password_hash": generate_password_hash(password),
            "username":  username,
            "twitter":   twitter.lstrip("@").strip(),
            "instagram": instagram.lstrip("@").strip(),
            "tiktok":    tiktok.lstrip("@").strip(),
        }).execute()
        return True, ""
    except Exception as e:
        print(f"register_user error: {e}")
        return False, "Something went wrong. Please try again."


def login_user(email, password):
    try:
        res = get_db().table("users").select("*").eq("email", email.lower().strip()).execute()
        if not res.data:
            return None, "No account found with that email."
        user = res.data[0]
        if not check_password_hash(user["password_hash"], password):
            return None, "Incorrect password."
        return user, ""
    except Exception as e:
        print(f"login_user error: {e}")
        return None, "Something went wrong. Please try again."


def get_user(username):
    try:
        res = get_db().table("users").select("*").eq("username", username).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def update_profile(username, twitter="", instagram="", tiktok="",
                   bank_name="", bank_account="", new_password=None):
    try:
        updates = {
            "twitter":      twitter.lstrip("@").strip(),
            "instagram":    instagram.lstrip("@").strip(),
            "tiktok":       tiktok.lstrip("@").strip(),
            "bank_name":    bank_name.strip(),
            "bank_account": bank_account.strip(),
        }
        if new_password:
            updates["password_hash"] = generate_password_hash(new_password)
        get_db().table("users").update(updates).eq("username", username).execute()
        return True, ""
    except Exception as e:
        print(f"update_profile error: {e}")
        return False, "Could not save changes. Please try again."


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


PAYOUTS = {
    "result":      400,   # H/D/A correct
    "exact_score": 1600,  # exact scoreline correct
    "over_under":  200,   # over/under 2.5 correct
    "goals_range": 300,   # goals range correct
}

def _goals_range(total):
    if total <= 1:  return "0-1"
    elif total <= 3: return "2-3"
    elif total <= 5: return "4-5"
    else:           return "6+"

def calculate_payout(tip, actual_home, actual_away):
    """Calculate total payout in Naira for a settled tip."""
    actual_result = "H" if actual_home > actual_away else ("A" if actual_away > actual_home else "D")
    ph, pa = int(tip["home_goals"]), int(tip["away_goals"])
    payout = 0
    breakdown = {}

    if tip["result_pick"] == actual_result:
        payout += PAYOUTS["result"]
        breakdown["Match Result"] = PAYOUTS["result"]

    if ph == actual_home and pa == actual_away:
        payout += PAYOUTS["exact_score"]
        breakdown["Exact Score"] = PAYOUTS["exact_score"]

    if (ph + pa > 2.5) == (actual_home + actual_away > 2.5):
        payout += PAYOUTS["over_under"]
        breakdown["Over/Under 2.5"] = PAYOUTS["over_under"]

    if _goals_range(ph + pa) == _goals_range(actual_home + actual_away):
        payout += PAYOUTS["goals_range"]
        breakdown["Goals Range"] = PAYOUTS["goals_range"]

    return payout, breakdown


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
