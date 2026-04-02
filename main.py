import streamlit as st
import pandas as pd
from database import (
    init_db,
    get_all_players,
    get_player_stats,
    get_user_grade,
    submit_grade,
    get_leaderboard,
    GRADE_VALUES,
    numeric_to_letter,
)

# Bootstrap
init_db()

st.set_page_config(
    page_title="CFB Draft Grades",
    page_icon="🏈",
    layout="wide",
)

GRADES = list(GRADE_VALUES.keys())

POSITION_ORDER = ["QB", "RB", "WR", "TE", "OT", "IOL", "EDGE", "DT", "LB", "CB", "S"]

GRADE_COLOR = {
    "A+": "#2ecc71", "A": "#27ae60", "A-": "#52be80",
    "B+": "#3498db", "B": "#2980b9", "B-": "#5dade2",
    "C+": "#f39c12", "C": "#e67e22", "C-": "#e59866",
    "D":  "#e74c3c", "F": "#c0392b",
}

if "username" not in st.session_state:
    st.session_state.username = ""

st.title("🏈 CFB Draft Grades")
st.caption("Crowdsourced NFL Draft grades for college football prospects")

st.divider()

with st.sidebar:
    st.header("Your Identity")
    username_input = st.text_input(
        "Username",
        value=st.session_state.username,
        placeholder="e.g. DraftScout99",
        help="Required to submit grades. One grade per prospect.",
    )
    if username_input:
        st.session_state.username = username_input.strip()

    if st.session_state.username:
        st.success(f"Signed in as **{st.session_state.username}**")
    else:
        st.info("Enter a username to submit grades.")

    st.divider()
    st.header("Filter")
    all_players = get_all_players()
    positions = sorted(
        set(p[2] for p in all_players),
        key=lambda x: POSITION_ORDER.index(x) if x in POSITION_ORDER else 99,
    )
    selected_positions = st.multiselect(
        "Position", positions, default=positions
    )
    search = st.text_input("Search player", placeholder="Name or school...")

tab_grade, tab_leaderboard = st.tabs(["Grade Prospects", "Leaderboard"])

with tab_grade:
    filtered = [
        p for p in all_players
        if p[2] in selected_positions
        and (not search or search.lower() in p[1].lower() or search.lower() in p[3].lower())
    ]

    if not filtered:
        st.warning("No prospects match your filters.")
    else:
        by_position: dict = {}
        for pid, name, pos, college in filtered:
            by_position.setdefault(pos, []).append((pid, name, pos, college))

        for pos in POSITION_ORDER:
            if pos not in by_position:
                continue
            st.subheader(pos)
            for pid, name, pos_, college in by_position[pos]:
                count, avg_num, dist = get_player_stats(pid)
                user_grade = (
                    get_user_grade(pid, st.session_state.username)
                    if st.session_state.username
                    else None
                )

                with st.container(border=True):
                    col_info, col_community, col_submit = st.columns([3, 3, 2])

                    with col_info:
                        st.markdown(f"**{name}**")
                        st.caption(f"{college} · {pos_}")

                    with col_community:
                        if count == 0:
                            st.markdown("*No grades yet -- be first!*")
                        else:
                            avg_letter = numeric_to_letter(avg_num)
                            color = GRADE_COLOR.get(avg_letter, "#888")
                            st.markdown(
                                f"Community grade: "
                                f"<span style='font-size:1.4rem;font-weight:700;"
                                f"color:{color}'>{avg_letter}</span> "
                                f"<span style='color:#888'>({count} vote{'s' if count != 1 else ''})</span>",
                                unsafe_allow_html=True,
                            )
                            if dist:
                                dist_data = {g: dist.get(g, 0) for g in GRADES}
                                df_dist = pd.DataFrame(
                                    {"Grade": list(dist_data.keys()), "Votes": list(dist_data.values())}
                                )
                                st.bar_chart(df_dist.set_index("Grade"), height=80, use_container_width=True)

                    with col_submit:
                        if not st.session_state.username:
                            st.caption("Set a username to grade")
                        else:
                            default_idx = (
                                GRADES.index(user_grade) if user_grade in GRADES else 0
                            )
                            selected = st.selectbox(
                                "Your grade",
                                GRADES,
                                index=default_idx,
                                key=f"grade_{pid}",
                                label_visibility="collapsed",
                            )
                            btn_label = "Update" if user_grade else "Submit"
                            if st.button(btn_label, key=f"btn_{pid}"):
                                if submit_grade(pid, st.session_state.username, selected):
                                    st.success(f"Graded {name}: {selected}")
                                    st.rerun()
                                else:
                                    st.error("Failed to save grade.")

with tab_leaderboard:
    board = get_leaderboard()

    if not board:
        st.info("No grades submitted yet. Head to the Grade Prospects tab to get started!")
    else:
        st.subheader("Top-Graded Prospects")
        st.caption("Ranked by community average grade (minimum 1 vote)")

        df = pd.DataFrame(board, columns=["Player", "Position", "College", "Votes", "Avg Grade"])
        df.insert(0, "Rank", range(1, len(df) + 1))

        def color_grade(val):
            c = GRADE_COLOR.get(val, "#888")
            return f"color: {c}; font-weight: bold"

        st.dataframe(
            df.style.map(color_grade, subset=["Avg Grade"]),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("Grade Distribution by Position")
        all_p = get_all_players()
        rows_pos = []
        for pid, name, pos, college in all_p:
            count, avg_num, _ = get_player_stats(pid)
            if count > 0:
                rows_pos.append({"Position": pos, "Avg Numeric": avg_num, "Count": count})

        if rows_pos:
            df_pos = pd.DataFrame(rows_pos)
            pos_avg = (
                df_pos.groupby("Position")
                .apply(lambda g: (g["Avg Numeric"] * g["Count"]).sum() / g["Count"].sum())
                .reset_index()
                .rename(columns={0: "Weighted Avg"})
            )
            pos_avg = pos_avg.sort_values("Weighted Avg", ascending=False)
            st.bar_chart(pos_avg.set_index("Position")["Weighted Avg"], use_container_width=True)
