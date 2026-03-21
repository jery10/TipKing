import os
import traceback
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from db import (submit_tip, get_tips_for_match, has_tipped, get_my_tips,
                get_leaderboard, get_all_tips, get_recent_winners, get_stats, mark_result)
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
        fixtures=fixtures, handle=get_handle())


@app.route("/set-handle", methods=["POST"])
def set_handle():
    handle = request.form.get("handle", "").lstrip("@").lower().strip()
    if handle:
        session["handle"] = handle
    next_page = request.form.get("next", "/")
    return redirect(next_page)


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
        comp_filter=comp_filter, handle=get_handle())


@app.route("/match/<path:home_team>/vs/<path:away_team>")
def match_page(home_team, away_team):
    tips = get_tips_for_match(home_team, away_team)
    con = consensus(tips)
    already = has_tipped(get_handle(), home_team, away_team) if get_handle() else False
    my_tip = None
    if already and get_handle():
        my_tips = get_my_tips(get_handle())
        for t in my_tips:
            if t["home_team"] == home_team and t["away_team"] == away_team:
                my_tip = t
                break
    return render_template("match.html",
        home=home_team, away=away_team,
        tips=tips, consensus=con,
        already=already, my_tip=my_tip,
        handle=get_handle())


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    handle = get_handle() or data.get("handle", "")
    if not handle:
        return jsonify({"ok": False, "error": "No handle set"})

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
    return render_template("leaderboard.html",
        leaderboard=lb, stats=stats, handle=get_handle())


@app.route("/my-tips", methods=["GET", "POST"])
def my_tips():
    handle = get_handle()
    tips = []
    accuracy = 0
    correct = 0
    if handle:
        tips = get_my_tips(handle)
        settled = [t for t in tips if t.get("is_correct") is not None]
        correct = sum(1 for t in settled if t["is_correct"])
        accuracy = round(correct / len(settled) * 100, 1) if settled else 0
    return render_template("my_tips.html",
        handle=handle, tips=tips,
        accuracy=accuracy, correct=correct)


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
    for tip in match_tips:
        mark_result(tip["id"], tip["result_pick"] == actual_result, actual_home, actual_away)
        count += 1
    return jsonify({"ok": True, "settled": count})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
