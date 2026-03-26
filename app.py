import os
import traceback
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from db import (submit_tip, get_tips_for_match, has_tipped, get_my_tips,
                get_leaderboard, get_all_tips, get_recent_winners, get_stats,
                mark_result, calculate_payout, register_user, login_user,
                get_user, update_profile, vote_tip, get_live_tips)
from fixtures import get_upcoming, COMPETITIONS
import settler

load_dotenv()
settler.start_background()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "predict4free-secret-2024")

# ── Seed data shown when leaderboard / match feed is sparse ──────────────────

_SEED_LEADERBOARD = [
    {"handle": "emeka_predict",  "tips": 34, "correct": 26, "accuracy": 76.5, "seed": True},
    {"handle": "tunde_tipmaster","tips": 29, "correct": 21, "accuracy": 72.4, "seed": True},
    {"handle": "chidi_fc",       "tips": 41, "correct": 29, "accuracy": 70.7, "seed": True},
    {"handle": "abuja_punter",   "tips": 22, "correct": 15, "accuracy": 68.2, "seed": True},
    {"handle": "lagos_oracle",   "tips": 37, "correct": 25, "accuracy": 67.6, "seed": True},
    {"handle": "femi_goals",     "tips": 18, "correct": 12, "accuracy": 66.7, "seed": True},
    {"handle": "ndidi_analyst",  "tips": 26, "correct": 17, "accuracy": 65.4, "seed": True},
    {"handle": "kano_tipster",   "tips": 31, "correct": 20, "accuracy": 64.5, "seed": True},
    {"handle": "seun_predictor", "tips": 15, "correct":  9, "accuracy": 60.0, "seed": True},
    {"handle": "ph_baller",      "tips": 20, "correct": 12, "accuracy": 60.0, "seed": True},
]

_SEED_MATCHES = [
    {
        "home": "Arsenal", "away": "Chelsea", "date": "2026-03-15",
        "tips": [
            {"handle": "emeka_predict",   "result_pick": "H", "home_goals": 2, "away_goals": 1,
             "confidence": 4, "is_correct": True,  "actual_home": 2, "actual_away": 1, "reasoning": "Arsenal at home are unstoppable this season"},
            {"handle": "tunde_tipmaster","result_pick": "H", "home_goals": 1, "away_goals": 0,
             "confidence": 3, "is_correct": True,  "actual_home": 2, "actual_away": 1, "reasoning": ""},
            {"handle": "chidi_fc",       "result_pick": "D", "home_goals": 1, "away_goals": 1,
             "confidence": 2, "is_correct": False, "actual_home": 2, "actual_away": 1, "reasoning": "Both teams in good form"},
            {"handle": "lagos_oracle",   "result_pick": "A", "home_goals": 0, "away_goals": 1,
             "confidence": 3, "is_correct": False, "actual_home": 2, "actual_away": 1, "reasoning": "Chelsea away record is strong"},
            {"handle": "femi_goals",     "result_pick": "H", "home_goals": 3, "away_goals": 1,
             "confidence": 5, "is_correct": True,  "actual_home": 2, "actual_away": 1, "reasoning": "Gunners to dominate"},
        ]
    },
    {
        "home": "Real Madrid", "away": "Barcelona", "date": "2026-03-08",
        "tips": [
            {"handle": "abuja_punter",   "result_pick": "H", "home_goals": 2, "away_goals": 0,
             "confidence": 4, "is_correct": True,  "actual_home": 3, "actual_away": 1, "reasoning": "Clasico at Bernabeu, Madrid always deliver"},
            {"handle": "ndidi_analyst",  "result_pick": "H", "home_goals": 3, "away_goals": 1,
             "confidence": 5, "is_correct": True,  "actual_home": 3, "actual_away": 1, "reasoning": "Predicted this exact score — Vinicius hat-trick incoming"},
            {"handle": "kano_tipster",   "result_pick": "D", "home_goals": 1, "away_goals": 1,
             "confidence": 3, "is_correct": False, "actual_home": 3, "actual_away": 1, "reasoning": ""},
            {"handle": "seun_predictor", "result_pick": "A", "home_goals": 1, "away_goals": 2,
             "confidence": 2, "is_correct": False, "actual_home": 3, "actual_away": 1, "reasoning": "Barca have Yamal in form"},
            {"handle": "ph_baller",      "result_pick": "H", "home_goals": 2, "away_goals": 1,
             "confidence": 4, "is_correct": True,  "actual_home": 3, "actual_away": 1, "reasoning": ""},
        ]
    },
    {
        "home": "Manchester City", "away": "Liverpool", "date": "2026-03-01",
        "tips": [
            {"handle": "emeka_predict",  "result_pick": "D", "home_goals": 1, "away_goals": 1,
             "confidence": 3, "is_correct": True,  "actual_home": 1, "actual_away": 1, "reasoning": "This fixture always ends level at the Etihad"},
            {"handle": "chidi_fc",       "result_pick": "D", "home_goals": 2, "away_goals": 2,
             "confidence": 4, "is_correct": True,  "actual_home": 1, "actual_away": 1, "reasoning": "Two great teams, draw inevitable"},
            {"handle": "tunde_tipmaster","result_pick": "H", "home_goals": 2, "away_goals": 1,
             "confidence": 4, "is_correct": False, "actual_home": 1, "actual_away": 1, "reasoning": "City home form is too good"},
            {"handle": "femi_goals",     "result_pick": "A", "home_goals": 0, "away_goals": 2,
             "confidence": 3, "is_correct": False, "actual_home": 1, "actual_away": 1, "reasoning": ""},
            {"handle": "lagos_oracle",   "result_pick": "D", "home_goals": 0, "away_goals": 0,
             "confidence": 2, "is_correct": True,  "actual_home": 1, "actual_away": 1, "reasoning": "Both defences solid"},
        ]
    },
]

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

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "predict4free2024")


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
    handle = get_handle()
    raw_stats = get_stats()
    # Inflate stats with seed activity so the platform looks established
    stats = {
        "total":    raw_stats["total"]    + 312,
        "tipsters": raw_stats["tipsters"] + 48,
        "settled":  raw_stats["settled"]  + 187,
        "correct":  raw_stats["correct"]  + 103,
    }
    fixtures = get_upcoming(days=3)[:6]
    if fixtures:
        all_tips_batch = get_all_tips()
        tips_by_match = {}
        for t in all_tips_batch:
            key = (t["home_team"], t["away_team"])
            tips_by_match.setdefault(key, []).append(t)
        tipped_by_handle = {(t["home_team"], t["away_team"]) for t in all_tips_batch
                            if handle and t["handle"] == handle} if handle else set()
        for f in fixtures:
            key = (f["home_team"], f["away_team"])
            tips = tips_by_match.get(key, [])
            f["tip_count"] = len(tips)
            f["consensus"] = consensus(tips)
            f["already_tipped"] = key in tipped_by_handle

    my_stats = {"total": 0, "correct": 0, "accuracy": 0, "earned": 0}
    recent_tips = []
    if handle:
        my_tips_all = get_my_tips(handle)
        recent_tips = my_tips_all[:5]
        settled = [t for t in my_tips_all if t.get("is_correct") is not None]
        correct = sum(1 for t in settled if t["is_correct"])
        earned = sum(
            calculate_payout(t, t["actual_home"], t["actual_away"])[0]
            for t in settled if t.get("actual_home") is not None
        )
        my_stats = {
            "total": len(my_tips_all),
            "correct": correct,
            "accuracy": round(correct / len(settled) * 100, 1) if settled else 0,
            "earned": earned,
        }

    winners = get_recent_winners(6)
    # Seed winners for marketing when platform is new
    _seed_winners = [
        {"handle": "emeka_predict",   "home_team": "Arsenal",       "away_team": "Chelsea",       "result_pick": "H", "actual_home": 2, "actual_away": 1},
        {"handle": "ndidi_analyst",   "home_team": "Real Madrid",   "away_team": "Barcelona",     "result_pick": "H", "actual_home": 3, "actual_away": 1},
        {"handle": "emeka_predict",   "home_team": "Man City",      "away_team": "Liverpool",     "result_pick": "D", "actual_home": 1, "actual_away": 1},
        {"handle": "tunde_tipmaster", "home_team": "Arsenal",       "away_team": "Chelsea",       "result_pick": "H", "actual_home": 2, "actual_away": 1},
        {"handle": "abuja_punter",    "home_team": "Real Madrid",   "away_team": "Barcelona",     "result_pick": "H", "actual_home": 3, "actual_away": 1},
        {"handle": "chidi_fc",        "home_team": "Man City",      "away_team": "Liverpool",     "result_pick": "D", "actual_home": 1, "actual_away": 1},
    ]
    if len(winners) < 4:
        winners = winners + _seed_winners[:max(0, 6 - len(winners))]
    lb = get_leaderboard()[:5]
    # Pad homepage leaderboard preview with seed data
    real_handles = {r["handle"] for r in lb}
    if len(lb) < 5:
        for seed in _SEED_LEADERBOARD:
            if seed["handle"] not in real_handles and len(lb) < 5:
                lb.append(seed)
    return render_template("index.html",
        stats=stats, winners=winners, leaderboard=lb,
        fixtures=fixtures, my_stats=my_stats, recent_tips=recent_tips,
        handle=handle, twitter=get_twitter())


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


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    handle = get_handle()
    user = get_user(handle)
    success = None
    error = None
    form_type = None
    if request.method == "POST":
        form_type = request.form.get("form_type", "profile")
        if form_type == "payout":
            bank_name    = request.form.get("bank_name", "").strip()
            bank_account = request.form.get("bank_account", "").strip()
            existing = user or {}
            ok, error = update_profile(
                handle,
                twitter=existing.get("twitter", ""),
                bank_name=bank_name,
                bank_account=bank_account,
            )
            if ok:
                success = "payout"
                user = get_user(handle)
        else:
            twitter      = request.form.get("twitter", "").strip()
            new_password = request.form.get("new_password", "").strip()
            confirm_password = request.form.get("confirm_password", "").strip()
            if new_password and new_password != confirm_password:
                error = "Passwords don't match."
            elif new_password and len(new_password) < 6:
                error = "Password must be at least 6 characters."
            else:
                existing = user or {}
                ok, error = update_profile(
                    handle, twitter,
                    bank_name=existing.get("bank_name", ""),
                    bank_account=existing.get("bank_account", ""),
                    new_password=new_password if new_password else None,
                )
                if ok:
                    session["twitter"] = twitter.lstrip("@").strip()
                    success = "profile"
                    user = get_user(handle)
    return render_template("profile.html",
        user=user, success=success, error=error, form_type=form_type,
        handle=handle, twitter=get_twitter())


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

    # Batch-load all tips once instead of one query per fixture
    grouped = {}
    if all_fixtures:
        all_tips_batch = get_all_tips()
        tips_by_match = {}
        for t in all_tips_batch:
            key = (t["home_team"], t["away_team"])
            tips_by_match.setdefault(key, []).append(t)
        handle_now = get_handle()
        tipped_by_handle = {(t["home_team"], t["away_team"]) for t in all_tips_batch
                            if handle_now and t["handle"] == handle_now} if handle_now else set()
        for f in all_fixtures:
            d = str(f["date_only"])
            if d not in grouped:
                grouped[d] = {"label": f["date"].strftime("%A, %d %B %Y"), "matches": []}
            key = (f["home_team"], f["away_team"])
            tips = tips_by_match.get(key, [])
            f["tip_count"] = len(tips)
            f["consensus"] = consensus(tips)
            f["already_tipped"] = key in tipped_by_handle
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
    raw_handle = get_handle() or data.get("handle", "")
    if not raw_handle:
        return jsonify({"ok": False, "error": "No handle set"})
    # Always use just the username part (strips email domain from old sessions)
    handle = raw_handle.split("@")[0] if "@" in raw_handle else raw_handle

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

    if has_tipped(handle, home_team, away_team):
        return jsonify({"ok": False, "error": "You've already made a prediction for this match."})

    # Get real match date and competition from fixtures (never trust empty client value)
    match_fixture = next((f for f in upcoming if f["home_team"] == home_team and f["away_team"] == away_team), None)
    match_date = match_fixture["date_only"] if match_fixture else None
    competition = match_fixture["competition"] if match_fixture else data.get("competition", "")

    # Validate — at least one market must be picked
    result = data.get("result_pick") or None
    ou25   = data.get("ou25_pick") or None
    ou35   = data.get("ou35_pick") or None
    ou45   = data.get("ou45_pick") or None
    gr     = data.get("goals_range_pick") or None
    btts   = data.get("btts_pick") or None
    if not any([result, ou25, ou35, ou45, gr, btts]):
        return jsonify({"ok": False, "error": "Please pick a market before submitting."})

    has_score = data.get("has_score", False)
    hg = int(data["home_goals"]) if has_score and data.get("home_goals") is not None else None
    ag = int(data["away_goals"]) if has_score and data.get("away_goals") is not None else None
    # Validate score consistency only when both result AND score are provided
    if result and has_score and hg is not None and ag is not None:
        if result == "H" and hg <= ag:
            return jsonify({"ok": False, "error": "Score doesn't match Home Win"})
        if result == "A" and ag <= hg:
            return jsonify({"ok": False, "error": "Score doesn't match Away Win"})
        if result == "D" and hg != ag:
            return jsonify({"ok": False, "error": "Score doesn't match Draw"})

    result_obj = submit_tip(
        handle=handle,
        competition=competition,
        home_team=home_team,
        away_team=away_team,
        match_date=match_date,
        result_pick=result,
        home_goals=hg,
        away_goals=ag,
        confidence=data.get("confidence", 3),
        reasoning=data.get("reasoning", ""),
        ou25_pick=ou25,
        ou35_pick=ou35,
        ou45_pick=ou45,
        goals_range_pick=gr,
        btts_pick=btts,
    )
    if result_obj is True:
        return jsonify({"ok": True})
    elif isinstance(result_obj, tuple):
        return jsonify({"ok": False, "error": result_obj[1]})
    return jsonify({"ok": False, "error": "Could not save prediction. Please try again."})


@app.route("/leaderboard")
def leaderboard():
    lb = get_leaderboard()

    # Pad leaderboard with seed data until we have at least 10 real entries
    real_handles = {r["handle"] for r in lb}
    if len(lb) < 10:
        for seed in _SEED_LEADERBOARD:
            if seed["handle"] not in real_handles:
                lb.append(seed)
        lb.sort(key=lambda x: (-x["accuracy"], -x["correct"]))
        lb = lb[:10]

    # Live predictions feed — pending tips, sorted by votes then recency
    live = get_live_tips(limit=50)
    live.sort(key=lambda t: (-(t.get("upvotes") or 0) + (t.get("downvotes") or 0)))

    # Read voted tip IDs from session so buttons show correct state
    voted = session.get("voted", {})

    return render_template("leaderboard.html",
        leaderboard=lb, live=live, voted=voted,
        handle=get_handle(), twitter=get_twitter())


@app.route("/vote", methods=["POST"])
def vote():
    data = request.get_json()
    tip_id = data.get("tip_id")
    direction = data.get("direction")
    if not tip_id or direction not in ("up", "down"):
        return jsonify({"ok": False})
    # Track voted tips in session to prevent repeat votes
    voted = session.get("voted", {})
    key = str(tip_id)
    if key in voted:
        return jsonify({"ok": False, "error": "already_voted"})
    ok = vote_tip(tip_id, direction)
    if ok:
        voted[key] = direction
        session["voted"] = voted
    return jsonify({"ok": ok})


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


@app.route("/admin/auto-settle", methods=["POST"])
def admin_auto_settle():
    if not session.get("admin"):
        return jsonify({"ok": False})
    try:
        n = settler.auto_settle()
        log = settler._last_run.get("log", [])
        return jsonify({"ok": True, "settled": n, "log": log})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ── Public API — read by BetPredict ──────────────────────────────────────────

def _fuzzy_match(name, stored):
    """True if name loosely matches stored — handles 'Liverpool' vs 'Liverpool FC' etc."""
    a, b = name.lower().strip(), stored.lower().strip()
    return a == b or a in b or b in a

@app.route("/api/match/<path:home_team>/vs/<path:away_team>")
def api_match(home_team, away_team):
    """Public endpoint: crowd consensus + reasoning for a match."""
    # Try exact match first, then fuzzy fallback
    tips = get_tips_for_match(home_team, away_team)
    if not tips:
        all_tips = get_all_tips()
        tips = [t for t in all_tips
                if _fuzzy_match(home_team, t["home_team"])
                and _fuzzy_match(away_team, t["away_team"])]

    con = consensus(tips)
    pending = [t for t in tips if t.get("is_correct") is None]
    reasons = [t["reasoning"] for t in pending if t.get("reasoning", "").strip()]

    # Safe avg for nullable home_goals/away_goals
    scored = [t for t in pending if t.get("home_goals") is not None and t.get("away_goals") is not None]
    return jsonify({
        "home": home_team,
        "away": away_team,
        "matched_home": tips[0]["home_team"] if tips else home_team,
        "matched_away": tips[0]["away_team"] if tips else away_team,
        "total_predictions": len(tips),
        "pending": len(pending),
        "consensus": {
            "home_win_pct": con["H"],
            "draw_pct":     con["D"],
            "away_win_pct": con["A"],
            "top_pick":     con["top"],
        },
        "avg_predicted_home": round(sum(t["home_goals"] for t in scored) / len(scored), 2) if scored else None,
        "avg_predicted_away": round(sum(t["away_goals"] for t in scored) / len(scored), 2) if scored else None,
        "over_25_pct": round(sum(1 for t in scored if t["home_goals"] + t["away_goals"] > 2.5) / len(scored) * 100) if scored else None,
        "reasoning": reasons[:10],
    })


@app.route("/api/stats")
def api_stats():
    """Public stats endpoint for BetPredict dashboard."""
    return jsonify(get_stats())


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", handle=get_handle(), twitter=get_twitter())


@app.route("/terms")
def terms():
    return render_template("terms.html", handle=get_handle(), twitter=get_twitter())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
