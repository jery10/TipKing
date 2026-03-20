import streamlit as st
import pandas as pd
from db import (
    submit_tip, get_tips_for_match, get_my_tips,
    get_leaderboard, get_all_tips, mark_result, has_already_tipped
)
from fixtures import get_upcoming, COMPETITIONS

st.set_page_config(
    page_title="TipKing",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
* { font-family: 'Inter', sans-serif; }

.hero {
    background: linear-gradient(135deg, #FFD700 0%, #FF8C00 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 24px;
    color: #0a0a0a;
}
.hero h1 { font-size: 2.4rem; font-weight: 900; margin: 0; }
.hero p  { font-size: 1.05rem; margin: 6px 0 0 0; font-weight: 500; }

.match-card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.match-card:hover { border-color: #FFD700; }

.teams { font-size: 1.15rem; font-weight: 700; color: #fff; }
.kickoff { font-size: 0.82rem; color: #888; margin-top: 2px; }

.tip-row {
    background: #111;
    border-left: 3px solid #FFD700;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 0.9rem;
}
.correct   { border-left-color: #00C851 !important; }
.incorrect { border-left-color: #ff4444 !important; }
.pending   { border-left-color: #FFD700 !important; }

.leaderboard-row { font-size: 0.95rem; }
.gold   { color: #FFD700; font-weight: 800; }
.silver { color: #C0C0C0; font-weight: 700; }
.bronze { color: #CD7F32; font-weight: 700; }

.stat-box {
    background: #1a1a1a;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.stat-num { font-size: 2rem; font-weight: 900; color: #FFD700; }
.stat-label { font-size: 0.8rem; color: #888; margin-top: 2px; }

.pill-H { background:#00C851; color:#000; padding:2px 10px; border-radius:12px; font-size:0.82rem; font-weight:700; }
.pill-D { background:#FFD700; color:#000; padding:2px 10px; border-radius:12px; font-size:0.82rem; font-weight:700; }
.pill-A { background:#ff6b6b; color:#000; padding:2px 10px; border-radius:12px; font-size:0.82rem; font-weight:700; }

.conf-star { color: #FFD700; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.markdown("## 👑 TipKing")
st.sidebar.markdown("Submit tips. Win rewards.")
st.sidebar.markdown("---")

page = st.sidebar.radio("Navigate", [
    "🏠 Home — Submit Tips",
    "🏆 Leaderboard",
    "📋 My Tips",
    "🔐 Admin",
])

# Twitter handle (persisted in session)
st.sidebar.markdown("---")
st.sidebar.markdown("**Your Twitter handle**")
handle_input = st.sidebar.text_input(
    "Twitter handle", value=st.session_state.get("handle", ""),
    placeholder="@yourhandle", label_visibility="collapsed"
)
if handle_input:
    st.session_state["handle"] = handle_input.lstrip("@").lower()

st.sidebar.markdown("---")
st.sidebar.markdown(
    "📊 [View Statistical Predictions](https://betpredict.streamlit.app)",
    unsafe_allow_html=False,
)
st.sidebar.caption("Predictions are free. Winners get rewarded.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def handle_ok():
    return bool(st.session_state.get("handle", "").strip())

def pill(result):
    cls = {"H": "pill-H", "D": "pill-D", "A": "pill-A"}.get(result, "pill-D")
    label = {"H": "Home Win", "D": "Draw", "A": "Away Win"}.get(result, result)
    return f'<span class="{cls}">{label}</span>'

def stars(n):
    return "★" * n + "☆" * (5 - n)

def consensus_bar(tips_df):
    if tips_df.empty:
        return
    counts = tips_df["result_pick"].value_counts()
    total = len(tips_df)
    h = counts.get("H", 0)
    d = counts.get("D", 0)
    a = counts.get("A", 0)
    st.markdown(
        f'<div style="font-size:0.82rem;color:#888;margin:4px 0">'
        f'👥 {total} tip{"s" if total != 1 else ""} — '
        f'<span style="color:#00C851">Home {h}</span> · '
        f'<span style="color:#FFD700">Draw {d}</span> · '
        f'<span style="color:#ff6b6b">Away {a}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── PAGE: Home — Submit Tips ──────────────────────────────────────────────────

if page == "🏠 Home — Submit Tips":
    st.markdown("""
    <div class="hero">
        <h1>👑 TipKing</h1>
        <p>Submit your football predictions. The best tipsters get rewarded.</p>
    </div>
    """, unsafe_allow_html=True)

    if not handle_ok():
        st.warning("👈 Enter your Twitter handle in the sidebar to submit tips.")

    # Competition filter
    comp_options = {f"{v['flag']} {v['name']}": k for k, v in COMPETITIONS.items()}
    col1, col2 = st.columns([2, 3])
    with col1:
        comp_label = st.selectbox("Competition", list(comp_options.keys()), index=0)
    comp = comp_options[comp_label]

    with st.spinner("Loading fixtures..."):
        fixtures = get_upcoming(comp, days=14)

    if fixtures.empty:
        st.info("No upcoming fixtures found for this competition.")
        st.stop()

    # Group by date
    fixtures["date_only"] = fixtures["date"].dt.date
    for date_val, day_fx in sorted(fixtures.groupby("date_only"), key=lambda x: x[0]):
        date_str = pd.Timestamp(date_val).strftime("%A %d %B %Y")
        st.markdown(
            f'<div style="background:#FFD700;color:#000;font-weight:800;font-size:0.95rem;'
            f'padding:7px 14px;border-radius:8px;margin:20px 0 10px 0">📅 {date_str}</div>',
            unsafe_allow_html=True,
        )

        for _, fix in day_fx.iterrows():
            home, away = fix["home_team"], fix["away_team"]
            kickoff = fix["date"].strftime("%H:%M UTC")

            existing = get_tips_for_match(home, away)

            with st.container():
                st.markdown(
                    f'<div class="teams">{home} <span style="color:#FFD700">vs</span> {away}</div>'
                    f'<div class="kickoff">⏰ {kickoff}</div>',
                    unsafe_allow_html=True,
                )
                consensus_bar(existing)

                already = handle_ok() and has_already_tipped(
                    st.session_state["handle"], home, away
                )

                if already:
                    my = get_my_tips(st.session_state["handle"])
                    my = my[(my["home_team"] == home) & (my["away_team"] == away)]
                    if not my.empty:
                        r = my.iloc[0]
                        st.markdown(
                            f'✅ Your tip: {pill(r["result_pick"])} &nbsp; '
                            f'{r["home_goals"]}–{r["away_goals"]} &nbsp; '
                            f'<span class="conf-star">{stars(int(r["confidence"]))}</span>',
                            unsafe_allow_html=True,
                        )
                else:
                    with st.expander(f"➕ Submit tip for {home} vs {away}"):
                        if not handle_ok():
                            st.warning("Enter your Twitter handle in the sidebar first.")
                        else:
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                result = st.radio(
                                    "Prediction",
                                    ["Home Win", "Draw", "Away Win"],
                                    key=f"res_{home}_{away}",
                                    horizontal=True,
                                )
                            result_code = {"Home Win": "H", "Draw": "D", "Away Win": "A"}[result]

                            with c2:
                                hg = st.number_input(f"{home} goals", 0, 15, 1, key=f"hg_{home}_{away}")
                            with c3:
                                ag = st.number_input(f"{away} goals", 0, 15, 1, key=f"ag_{home}_{away}")

                            # Validate score matches result
                            score_ok = True
                            if result_code == "H" and hg <= ag:
                                st.warning("Home win selected but score shows draw or away win.")
                                score_ok = False
                            elif result_code == "A" and ag <= hg:
                                st.warning("Away win selected but score shows draw or home win.")
                                score_ok = False
                            elif result_code == "D" and hg != ag:
                                st.warning("Draw selected but goals are not equal.")
                                score_ok = False

                            conf = st.slider(
                                "Confidence", 1, 5, 3,
                                key=f"conf_{home}_{away}",
                                help="1 = guess, 5 = very confident",
                            )
                            st.caption(f"Confidence: {stars(conf)}")

                            reasoning = st.text_area(
                                "Why? (optional but helps)",
                                key=f"reason_{home}_{away}",
                                placeholder="e.g. City have full squad, Arsenal missing Saka, last 3 H2H all under 2.5...",
                                height=80,
                            )

                            if st.button(f"👑 Submit Tip", key=f"submit_{home}_{away}",
                                         type="primary", disabled=not score_ok):
                                ok = submit_tip(
                                    handle=st.session_state["handle"],
                                    competition=comp,
                                    home_team=home,
                                    away_team=away,
                                    match_date=str(fix["date"].date()),
                                    result_pick=result_code,
                                    home_goals=int(hg),
                                    away_goals=int(ag),
                                    confidence=conf,
                                    reasoning=reasoning,
                                )
                                if ok:
                                    st.success("✅ Tip submitted! Good luck 👑")
                                    st.rerun()
                                else:
                                    st.error("Failed to submit. Try again.")

                st.markdown("<hr style='border-color:#2a2a2a;margin:10px 0'>", unsafe_allow_html=True)


# ── PAGE: Leaderboard ─────────────────────────────────────────────────────────

elif page == "🏆 Leaderboard":
    st.markdown("## 🏆 TipKing Leaderboard")
    st.caption("Ranked by accuracy. Minimum 3 settled tips to qualify.")

    lb = get_leaderboard()

    if lb.empty:
        st.info("No settled tips yet. Check back after matches are played.")
    else:
        # Filter min 3 tips
        lb = lb[lb["Tips"] >= 3].reset_index(drop=True)
        lb.index += 1

        # Top 3 medals
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for i, row in lb.head(3).iterrows():
            medal = medals.get(i, "")
            st.markdown(
                f'<div style="background:#1a1a1a;border-radius:10px;padding:14px 20px;'
                f'margin-bottom:8px;border:1px solid #FFD700">'
                f'{medal} <b style="color:#FFD700;font-size:1.1rem">@{row["Twitter"]}</b>'
                f' &nbsp; {row["Accuracy %"]}% accuracy &nbsp;·&nbsp; '
                f'{row["Correct"]}/{row["Tips"]} tips correct'
                f'</div>',
                unsafe_allow_html=True,
            )

        if len(lb) > 3:
            st.markdown("---")
            st.dataframe(lb, use_container_width=True)

    # Global stats
    st.markdown("---")
    all_tips = get_all_tips()
    if not all_tips.empty:
        total = len(all_tips)
        settled = all_tips["is_correct"].notna().sum()
        correct = all_tips["is_correct"].sum() if settled > 0 else 0
        users = all_tips["handle"].nunique()

        c1, c2, c3, c4 = st.columns(4)
        for col, num, label in [
            (c1, total, "Total Tips"),
            (c2, settled, "Settled"),
            (c3, f"{int(correct)}", "Correct"),
            (c4, users, "Tipsters"),
        ]:
            col.markdown(
                f'<div class="stat-box"><div class="stat-num">{num}</div>'
                f'<div class="stat-label">{label}</div></div>',
                unsafe_allow_html=True,
            )


# ── PAGE: My Tips ─────────────────────────────────────────────────────────────

elif page == "📋 My Tips":
    st.markdown("## 📋 My Tips")

    if not handle_ok():
        st.warning("Enter your Twitter handle in the sidebar.")
        st.stop()

    handle = st.session_state["handle"]
    st.markdown(f"Showing tips for **@{handle}**")

    tips = get_my_tips(handle)

    if tips.empty:
        st.info("No tips submitted yet. Go to Home to submit your first tip!")
        st.stop()

    # Stats
    settled = tips[tips["is_correct"].notna()]
    total = len(tips)
    correct = int(settled["is_correct"].sum()) if not settled.empty else 0
    accuracy = round(correct / len(settled) * 100, 1) if not settled.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Tips", total)
    c2.metric("Settled", len(settled))
    c3.metric("Correct", correct)
    c4.metric("Accuracy", f"{accuracy}%")

    st.markdown("---")

    for _, row in tips.iterrows():
        settled_flag = row["is_correct"]
        if settled_flag is True:
            status = "✅ Correct"
            card_class = "correct"
        elif settled_flag is False:
            status = "❌ Wrong"
            card_class = "incorrect"
        else:
            status = "⏳ Pending"
            card_class = "pending"

        actual = ""
        if pd.notna(row.get("actual_home")) and pd.notna(row.get("actual_away")):
            actual = f" · Actual: {int(row['actual_home'])}–{int(row['actual_away'])}"

        reasoning_str = f'<br><span style="color:#888;font-size:0.82rem">💬 {row["reasoning"]}</span>' \
            if row.get("reasoning") else ""

        st.markdown(
            f'<div class="tip-row {card_class}">'
            f'<b>{row["home_team"]} vs {row["away_team"]}</b> &nbsp;·&nbsp; {row["match_date"]}<br>'
            f'{pill(row["result_pick"])} &nbsp; {row["home_goals"]}–{row["away_goals"]} &nbsp; '
            f'<span class="conf-star">{stars(int(row["confidence"]))}</span> &nbsp; {status}{actual}'
            f'{reasoning_str}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── PAGE: Admin ───────────────────────────────────────────────────────────────

elif page == "🔐 Admin":
    st.markdown("## 🔐 Admin Panel")

    pwd = st.text_input("Password", type="password")
    try:
        import streamlit as st2
        admin_pwd = st2.secrets.get("ADMIN_PASSWORD", "tipking2024")
    except Exception:
        admin_pwd = "tipking2024"

    if pwd != admin_pwd:
        st.warning("Enter admin password to continue.")
        st.stop()

    st.success("Access granted.")

    all_tips = get_all_tips()
    if all_tips.empty:
        st.info("No tips submitted yet.")
        st.stop()

    # Consensus per match
    st.subheader("Match Consensus")
    matches = all_tips.groupby(["home_team", "away_team", "match_date"]).agg(
        Tips=("id", "count"),
        Home_Win=("result_pick", lambda x: (x == "H").sum()),
        Draw=("result_pick", lambda x: (x == "D").sum()),
        Away_Win=("result_pick", lambda x: (x == "A").sum()),
        Avg_Confidence=("confidence", "mean"),
    ).reset_index()
    matches["Top Pick"] = matches[["Home_Win", "Draw", "Away_Win"]].idxmax(axis=1)\
        .map({"Home_Win": "Home Win", "Draw": "Draw", "Away_Win": "Away Win"})
    matches["Avg_Confidence"] = matches["Avg_Confidence"].round(1)
    st.dataframe(matches, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Settle Results")
    st.caption("Mark tips correct/wrong after each match is played.")

    pending = all_tips[all_tips["is_correct"].isna()]
    if pending.empty:
        st.info("No pending tips to settle.")
    else:
        match_list = pending[["home_team", "away_team", "match_date"]]\
            .drop_duplicates().values.tolist()
        match_options = [f"{h} vs {a} ({d})" for h, a, d in match_list]
        selected = st.selectbox("Select match to settle", match_options)
        idx = match_options.index(selected)
        sel_home, sel_away, sel_date = match_list[idx]

        c1, c2 = st.columns(2)
        with c1:
            actual_home = st.number_input("Actual home goals", 0, 20, 0, key="ah")
        with c2:
            actual_away = st.number_input("Actual away goals", 0, 20, 0, key="aa")

        if st.button("✅ Settle this match", type="primary"):
            match_tips = pending[
                (pending["home_team"] == sel_home) &
                (pending["away_team"] == sel_away)
            ]
            if actual_home > actual_away:
                actual_result = "H"
            elif actual_away > actual_home:
                actual_result = "A"
            else:
                actual_result = "D"

            settled_count = 0
            for _, tip in match_tips.iterrows():
                is_correct = tip["result_pick"] == actual_result
                mark_result(tip["id"], is_correct, actual_home, actual_away)
                settled_count += 1
            st.success(f"Settled {settled_count} tips for {sel_home} vs {sel_away}")
            st.rerun()

    st.markdown("---")
    st.subheader("All Tips")
    cols_show = ["handle", "home_team", "away_team", "match_date",
                 "result_pick", "home_goals", "away_goals",
                 "confidence", "reasoning", "is_correct", "submitted_at"]
    cols_show = [c for c in cols_show if c in all_tips.columns]
    st.dataframe(all_tips[cols_show], use_container_width=True, hide_index=True)
