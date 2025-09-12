import streamlit as st
import pandas as pd
from datetime import datetime, date

# ------------------ CONFIG: REPLACE THESE ------------------
CSV_TEAMS       = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=0&single=true&output=csv"
CSV_WEEKS       = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=29563283&single=true&output=csv"
CSV_CHALLENGES  = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=570391343&single=true&output=csv"
# -----------------------------------------------------------

st.set_page_config(page_title="League Portal", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
  .stButton>button { padding: .9rem 1.1rem; font-size: 1rem; }
  .block-container { padding-top: .6rem; padding-bottom: 2.8rem; }
  .small-note { font-size: 0.9rem; opacity: 0.8; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def load_data():
    teams  = pd.read_csv(CSV_TEAMS)
    weeks  = pd.read_csv(CSV_WEEKS)
    chal   = pd.read_csv(CSV_CHALLENGES)

    # normalize columns
    for df in (teams, weeks, chal):
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # parse dates in weeks
    for c in ("start_date","end_date"):
        if c in weeks.columns:
            weeks[c] = pd.to_datetime(weeks[c]).dt.date

    # light type cleanup
    if "prize_amount" in chal.columns:
        chal["prize_amount"] = pd.to_numeric(chal["prize_amount"], errors="coerce")

    # winner_team_id numeric if possible
    if "winner_team_id" in chal.columns:
        chal["winner_team_id"] = pd.to_numeric(chal["winner_team_id"], errors="coerce")

    # eliminated_week optional
    if "eliminated_week" in teams.columns:
        teams["eliminated_week"] = pd.to_numeric(teams["eliminated_week"], errors="coerce")

    # paid column normalize to boolean if present
    if "paid" in chal.columns:
        chal["paid"] = chal["paid"].astype(str).str.strip().str.lower().isin(["y","yes","true","1"])

    return teams, weeks, chal

def current_week(weeks: pd.DataFrame, today: date) -> int | None:
    if weeks.empty:
        return None
    # if exact window match
    hit = weeks[(weeks["start_date"] <= today) & (today <= weeks["end_date"])]
    if not hit.empty:
        return int(hit.iloc[0]["week"])
    # else most recent started week, else earliest upcoming
    past = weeks[weeks["start_date"] <= today].sort_values("start_date")
    if not past.empty:
        return int(past.iloc[-1]["week"])
    return int(weeks.sort_values("start_date").iloc[0]["week"])

teams, weeks, chal = load_data()
today = datetime.now().date()
wk_default = current_week(weeks, today) if not weeks.empty else (int(chal["week"].max()) if "week" in chal else 1)

tab1, tab2, tab3 = st.tabs(["This Week", "Survivor", "Payouts by Team"])

# ---------------- This Week ----------------
with tab1:
    st.subheader("This Week")
    left, right = st.columns([1,2])
    with left:
        wk = st.number_input("Week", min_value=1, step=1, value=int(wk_default or 1))
        # show date range if available
        if not weeks.empty and "week" in weeks:
            row = weeks.loc[weeks["week"]==wk]
            if not row.empty:
                sd, ed = row.iloc[0].get("start_date", None), row.iloc[0].get("end_date", None)
                if pd.notna(sd) and pd.notna(ed):
                    st.markdown(f"<div class='small-note'>Dates: {sd} — {ed}</div>", unsafe_allow_html=True)

    wk_chal = chal[chal["week"] == wk].copy() if "week" in chal.columns else chal.copy()
    if wk_chal.empty:
        st.info("No challenges found for this week yet.")
    else:
        # Join winner name if you’ve set winner_team_id
        if "winner_team_id" in wk_chal.columns and "team_id" in teams.columns:
            wk_chal = wk_chal.merge(
                teams[["team_id","team_name"]],
                left_on="winner_team_id", right_on="team_id", how="left"
            )

        cols = []
        for c in ["challenge_name","description","prize_amount","team_name","winner_details","paid"]:
            if c in wk_chal.columns: cols.append(c)
        df_show = wk_chal[cols].rename(columns={
            "challenge_name":"Challenge",
            "description":"Description",
            "prize_amount":"Prize",
            "team_name":"Winner",
            "winner_details":"Details",
            "paid":"Paid"
        }).sort_values("Challenge")
        st.dataframe(df_show, use_container_width=True, height=380)

# ---------------- Survivor ----------------
with tab2:
    st.subheader("Survivor")
    # survivors = eliminated_week blank (or NaN)
    if "eliminated_week" not in teams.columns:
        st.info("Add 'eliminated_week' to the Teams sheet to enable Survivor view.")
    else:
        alive = teams[teams["eliminated_week"].isna()].copy().sort_values("team_name")
        st.markdown(f"**Still Alive ({len(alive)})**")
        cols_alive = [c for c in ["team_name","owner"] if c in alive.columns]
        st.dataframe(alive[cols_alive], use_container_width=True, height=260)

        out = teams.dropna(subset=["eliminated_week"]).copy()
        if not out.empty:
            out["eliminated_week"] = out["eliminated_week"].astype(int)
            # show optional score/note if you keep them
            elim_cols = ["eliminated_week","team_name"]
            for c in ["eliminated_score","eliminated_note"]:
                if c in out.columns: elim_cols.append(c)
            st.markdown("**Eliminations by Week**")
            st.dataframe(out.sort_values(["eliminated_week","team_name"])[elim_cols],
                         use_container_width=True, height=320)
        else:
            st.markdown("_No eliminations recorded yet._")

# ---------------- Payouts by Team ----------------
with tab3:
    st.subheader("Payouts by Team")
    if chal.empty or "winner_team_id" not in chal.columns or "prize_amount" not in chal.columns:
        st.info("To populate payouts, fill in 'winner_team_id' and 'prize_amount' in the Challenges sheet.")
    else:
        awarded = chal.dropna(subset=["winner_team_id"]).copy()
        awarded["winner_team_id"] = awarded["winner_team_id"].astype(int)

        # totals (awarded)
        by_team = awarded.groupby("winner_team_id", as_index=False)["prize_amount"].sum() \
            .rename(columns={"winner_team_id":"team_id","prize_amount":"Awarded"})

        # totals (paid) if you mark paid = TRUE
        if "paid" in awarded.columns:
            paid_totals = awarded[awarded["paid"]].groupby("winner_team_id", as_index=False)["prize_amount"].sum() \
                .rename(columns={"winner_team_id":"team_id","prize_amount":"Paid"})
            by_team = by_team.merge(paid_totals, on="team_id", how="left")
            by_team["Paid"] = by_team["Paid"].fillna(0)
        else:
            by_team["Paid"] = 0

        # join names & sort
        by_team = by_team.merge(teams[["team_id","team_name","owner"]], on="team_id", how="left") \
                         .sort_values(["Awarded","team_name"], ascending=[False, True])

        st.dataframe(by_team[["team_name","owner","Awarded","Paid"]],
                     use_container_width=True, height=420)

        # season totals row
        st.markdown("**Season Totals**")
        tot_awarded = float(by_team["Awarded"].sum())
        tot_paid    = float(by_team["Paid"].sum())
        st.write(f"- **Total Awarded:** ${tot_awarded:,.0f}")
        st.write(f"- **Total Paid:** ${tot_paid:,.0f}")