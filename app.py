import os
import traceback
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from db import (submit_tip, get_tips_for_match, has_tipped, get_my_tips,
                get_leaderboard, get_all_tips, get_recent_winners, get_stats,
                mark_result, calculate_payout, register_user, login_user)
from fixtures import get_upcoming, COMPETITIONS

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "tipking-secret-2024")

@app.errorhandler(Exception)
def handle_exception(e):
    traceback.print_exc()
    return f"<pre>500 Error:\n{traceback.format_exc()}</pre>", 500

@app.template_filter('username')
def username_filter(email):
    """Show only the part before @ for privacy."""
    if email and '@' in email:
        return email.split('@')[0]
    return email or 'anonymous'

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "tipking2024")


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_handle():
    return session.get("handle", "")

def get_twitter():
    return session.get("twitter", "")

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_handle():
            return redirect(f"/login?next={request.path}")
        return f(*args, **kwargs)
    return decorated

def consensus(tips):
    if not tips:
        return {"H": 0, "D": 0, "A": 0, "total": 0, "top": None}
    h = sum(1 for t in tips if t["result_pick"] == "H")
    d = sum(1 for t in tips if t["result_pick"] == "D")
    a = sum(1 for t in tips if t["result_pick"] == "A")
    total = len(tips)
    top = max([("H", h), ("D", d), ("A", a)], key=lambda x: x[1])[0] if total else None
    return {
        "H": round(h/total*100) if total else 0,
        "D": round(d/total*100) if total else 0,
        "A": round(a/total*100) if total else 0,
        "h_count": h, "d_count": d, "a_count": a,
        "total": total, "top": top,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    stats = get_stats()
    winners = get_recent_winners(6)
    lb = get_leaderboard()[:5]
    fixtures = get_upcoming(days=3)[:6]
    # Add tip counts to fixtures
    for f in fixtures:
        tips = get_tips_for_match(f["home_team"], f["away_team"])
        f["tip_count"] = len(tips)
        f["consensus"] = consensus(tips)
    return render_template("index.html",
        stats=stats, winners=winners, leaderboard=lb,
        fixtures=fixtures, handle=get_handle(), twitter=get_twitter())


@app.route("/register", methods=["GET", "POST"])
def register():
    if get_handle():
        return redirect("/")
    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        username = request.form.get("username", "").strip()
        twitter  = request.form.get("twitter", "").strip()
        if len(password) < 6:
            error = "Password must be at least 6 characters."
        elif not username:
            error = "Username is required."
        else:
            ok, error = register_user(email, password, username, twitter)
            if ok:
                session["handle"]  = username.lower().strip()
                session["twitter"] = twitter.lstrip("@").strip()
                return redirect("/")
    return render_template("register.html", error=error, twitter=get_twitter(), handle=get_handle())


@app.route("/login", methods=["GET", "POST"])
def login():
    if get_handle():
        return redirect("/")
    error = None
    next_page = request.args.get("next", "/")
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        next_page = request.form.get("next", "/")
        user, error = login_user(email, password)
        if user:
            session["handle"]  = user["username"]
            session["twitter"] = user.get("twitter", "")
            return redirect(next_page)
    return render_template("login.html", error=error, next=next_page, twitter=get_twitter(), handle=get_handle())


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/set-handle", methods=["POST"])
def set_handle():
    # Legacy redirect — send to register if not logged in
    if not get_handle():
        return redirect("/register")
    return redirect("/")


@app.route("/fixtures")
def fixtures_page():
    comp_filter = request.args.get("comp", "all")
    all_fixtures = get_upcoming(days=14)
    if comp_filter != "all":
        all_fixtures = [f for f in all_fixtures if f["competition"] == comp_filter]

    # Group by date
    from itertools import groupby
    grouped = {}
    for f in all_fixtures:
        d = str(f["date_only"])
        if d not in grouped:
            grouped[d] = {"label": f["date"].strftime("%A, %d %B %Y"), "matches": []}
        tips = get_tips_for_match(f["home_team"], f["away_team"])
        f["tip_count"] = len(tips)
        f["consensus"] = consensus(tips)
        f["already_tipped"] = has_tipped(get_handle(), f["home_team"], f["away_team"]) if get_handle() else False
        grouped[d]["matches"].append(f)

    return render_template("fixtures.html",
        grouped=grouped, competitions=COMPETITIONS,
        comp_filter=comp_filter, handle=get_handle(), twitter=get_twitter())


@app.route("/match/<path:home_team>/vs/<path:away_team>")
def match_page(home_team, away_team):
    tips = get_tips_for_match(home_team, away_team)
    con = consensus(tips)
    already = has_tipped(get_handle(), home_team, away_team) if get_handle() else False
    my_tip = None
    if already and get_handle():
        my_tips_list = get_my_tips(get_handle())
        for t in my_tips_list:
            if t["home_team"] == home_team and t["away_team"] == away_team:
                my_tip = t
                break
    upcoming = get_upcoming(days=14)
    is_open = any(f["home_team"] == home_team and f["away_team"] == away_team for f in upcoming)
    return render_template("match.html",
        home=home_team, away=away_team,
        tips=tips, consensus=con,
        already=already, my_tip=my_tip, is_open=is_open,
        handle=get_handle(), twitter=get_twitter())


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    handle = get_handle() or data.get("handle", "")
    if not handle:
        return jsonify({"ok": False, "error": "No handle set"})

    # Reject if match has kicked off (no longer in upcoming fixtures)
    home_team = data.get("home_team", "")
    away_team = data.get("away_team", "")
    upcoming = get_upcoming(days=14)
    match_open = any(
        f["home_team"] == home_team and f["away_team"] == away_team
        for f in upcoming
    )
    if not match_open:
        return jsonify({"ok": False, "error": "Predictions are closed — this match has already started or finished."})

    # Validate score matches result
    result = data.get("result_pick")
    hg = int(data.get("home_goals", 0))
    ag = int(data.get("away_goals", 0))
    if result == "H" and hg <= ag:
        return jsonify({"ok": False, "error": "Score doesn't match Home Win"})
    if result == "A" and ag <= hg:
        return jsonify({"ok": False, "error": "Score doesn't match Away Win"})
    if result == "D" and hg != ag:
        return jsonify({"ok": False, "error": "Score doesn't match Draw"})

    ok = submit_tip(
        handle=handle,
        competition=data.get("competition", ""),
        home_team=data.get("home_team"),
        away_team=data.get("away_team"),
        match_date=data.get("match_date"),
        result_pick=result,
        home_goals=hg,
        away_goals=ag,
        confidence=data.get("confidence", 3),
        reasoning=data.get("reasoning", ""),
    )
    return jsonify({"ok": ok})


@app.route("/leaderboard")
def leaderboard():
    lb = get_leaderboard()
    stats = get_stats()

    # Build "By Match" view — group all tips by match with payout per predictor
    all_tips = get_all_tips()
    matches_map = {}
    for t in all_tips:
        key = f"{t['home_team']}|{t['away_team']}"
        if key not in matches_map:
            matches_map[key] = {
                "home": t["home_team"],
                "away": t["away_team"],
                "date": t.get("match_date", ""),
                "tips": [],
            }
        tip_data = dict(t)
        if t.get("actual_home") is not None:
            tip_data["payout"], _ = calculate_payout(t, t["actual_home"], t["actual_away"])
        else:
            tip_data["payout"] = None
        matches_map[key]["tips"].append(tip_data)

    def _tip_sort(t):
        if t.get("is_correct") is True: return 0
        if t.get("is_correct") is None: return 1
        return 2

    match_list = list(matches_map.values())
    for m in match_list:
        m["tips"].sort(key=_tip_sort)
    match_list.sort(key=lambda m: m["date"] or "", reverse=True)

    return render_template("leaderboard.html",
        leaderboard=lb, stats=stats, match_list=match_list,
        handle=get_handle(), twitter=get_twitter())


@app.route("/my-tips", methods=["GET", "POST"])
def my_tips():
    handle = get_handle()
    tips = []
    accuracy = 0
    correct = 0
    total_earned = 0
    if handle:
        tips = get_my_tips(handle)
        settled = [t for t in tips if t.get("is_correct") is not None]
        correct = sum(1 for t in settled if t["is_correct"])
        accuracy = round(correct / len(settled) * 100, 1) if settled else 0
        for t in settled:
            if t.get("actual_home") is not None:
                p, _ = calculate_payout(t, t["actual_home"], t["actual_away"])
                total_earned += p
    return render_template("my_tips.html",
        handle=handle, tips=tips,
        accuracy=accuracy, correct=correct,
        total_earned=total_earned, twitter=get_twitter())


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST" and "password" in request.form:
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
        else:
            return render_template("admin.html", error="Wrong password", authed=False)

    if not session.get("admin"):
        return render_template("admin.html", authed=False)

    all_tips = get_all_tips()
    # Group pending by match
    pending_matches = {}
    for t in all_tips:
        if t.get("is_correct") is None:
            key = f"{t['home_team']} vs {t['away_team']}"
            if key not in pending_matches:
                pending_matches[key] = {
                    "home": t["home_team"], "away": t["away_team"],
                    "date": t.get("match_date", ""), "tips": []
                }
            pending_matches[key]["tips"].append(t)

    # Consensus per pending match
    for key, m in pending_matches.items():
        m["consensus"] = consensus(m["tips"])

    stats = get_stats()
    lb = get_leaderboard()[:10]
    return render_template("admin.html",
        authed=True, all_tips=all_tips,
        pending_matches=pending_matches,
        stats=stats, leaderboard=lb)


@app.route("/admin/settle", methods=["POST"])
def admin_settle():
    if not session.get("admin"):
        return jsonify({"ok": False})
    data = request.get_json()
    home = data["home"]
    away = data["away"]
    actual_home = int(data["actual_home"])
    actual_away = int(data["actual_away"])
    actual_result = "H" if actual_home > actual_away else ("A" if actual_away > actual_home else "D")

    all_tips = get_all_tips()
    match_tips = [t for t in all_tips
                  if t["home_team"] == home and t["away_team"] == away
                  and t.get("is_correct") is None]
    count = 0
    total_payout = 0
    for tip in match_tips:
        is_correct = tip["result_pick"] == actual_result
        payout, _ = calculate_payout(tip, actual_home, actual_away)
        mark_result(tip["id"], is_correct, actual_home, actual_away)
        total_payout += payout
        count += 1
    return jsonify({"ok": True, "settled": count, "total_payout": total_payout})


# ── Public API — read by BetPredict ──────────────────────────────────────────

@app.route("/api/match/<path:home_team>/vs/<path:away_team>")
def api_match(home_team, away_team):
    """Public endpoint: crowd consensus + reasoning for a match."""
    tips = get_tips_for_match(home_team, away_team)
    con = consensus(tips)
    pending = [t for t in tips if t.get("is_correct") is None]
    reasons = [t["reasoning"] for t in pending if t.get("reasoning", "").strip()]
    return jsonify({
        "home": home_team,
        "away": away_team,
        "total_predictions": len(tips),
        "pending": len(pending),
        "consensus": {
            "home_win_pct": con["H"],
            "draw_pct":     con["D"],
            "away_win_pct": con["A"],
            "top_pick":     con["top"],
        },
        "avg_predicted_home": round(sum(t["home_goals"] for t in pending) / len(pending), 2) if pending else None,
        "avg_predicted_away": round(sum(t["away_goals"] for t in pending) / len(pending), 2) if pending else None,
        "over_25_pct": round(sum(1 for t in pending if t["home_goals"] + t["away_goals"] > 2.5) / len(pending) * 100) if pending else None,
        "reasoning": reasons[:10],  # top 10 reasons
    })


@app.route("/api/stats")
def api_stats():
    """Public stats endpoint for BetPredict dashboard."""
    return jsonify(get_stats())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
