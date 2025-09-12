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

def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df

def _to_int_nullable(s: pd.Series) -> pd.Series:
    # Robustly coerce to pandas nullable Int64 (handles NaN)
    return pd.to_numeric(s, errors="coerce").astype("Int64")

def _to_bool_loose(s: pd.Series) -> pd.Series:
    # Accept y/yes/true/1 (case-insensitive) as True
    return s.astype(str).str.strip().str.lower().isin(["y", "yes", "true", "1"])

@st.cache_data(ttl=300)
def load_data():
    teams  = _norm_cols(pd.read_csv(CSV_TEAMS))
    weeks  = _norm_cols(pd.read_csv(CSV_WEEKS))
    chal   = _norm_cols(pd.read_csv(CSV_CHALLENGES))

    # Parse dates
    for c in ("start_date", "end_date"):
        if c in weeks.columns:
            weeks[c] = pd.to_datetime(weeks[c], errors="coerce").dt.date

    # Types for IDs and amounts
    if "team_id" in teams.columns:
        teams["team_id"] = _to_int_nullable(teams["team_id"])

    if "winner_team_id" in chal.columns:
        chal["winner_team_id"] = _to_int_nullable(chal["winner_team_id"])

    if "week" in chal.columns:
        chal["week"] = _to_int_nullable(chal["week"])

    if "week" in weeks.columns:
        weeks["week"] = _to_int_nullable(weeks["week"])

    if "prize_amount" in chal.columns:
        chal["prize_amount"] = pd.to_numeric(chal["prize_amount"], errors="coerce").fillna(0)

    # Survivor columns (optional)
    if "eliminated_week" in teams.columns:
        teams["eliminated_week"] = _to_int_nullable(teams["eliminated_week"])

    # Paid column (optional) -> boolean
    if "paid" in chal.columns:
        chal["paid"] = _to_bool_loose(chal["paid"])
    else:
        chal["paid"] = False

    return teams, weeks, chal

def current_week(weeks: pd.DataFrame, today: date) -> int | None:
    if weeks.empty or "start_date" not in weeks or "end_date" not in weeks:
        return None
    w = weeks[(weeks["start_date"] <= today) & (today <= weeks["end_date"])]
    if not w.empty:
        return int(w.iloc[0]["week"])
    past = weeks[weeks["start_date"] <= today].sort_values("start_date")
    if not past.empty:
        return int(past.iloc[-1]["week"])
    return int(weeks.sort_values("start_date").iloc[0]["week"])

# ---------- Load data ----------
try:
    teams, weeks, chal = load_data()
except Exception as e:
    st.error("Failed to load data. Check your CSV URLs and that each tab is published as CSV.")
    st.exception(e)
    st.stop()

today = datetime.now().date()
wk_default = current_week(weeks, today) if not weeks.empty else (
    int(chal["week"].dropna().max()) if "week" in chal.columns and not chal.empty else 1
)

tab1, tab2, tab3 = st.tabs(["This Week", "Survivor", "Payouts by Team"])

# ---------------- This Week ----------------
with tab1:
    st.subheader("This Week")

    left, right = st.columns([1, 2], gap="large")
    with left:
        wk = st.number_input("Week", min_value=1, step=1, value=int(wk_default or 1))
        if not weeks.empty and "week" in weeks.columns:
            row = weeks.loc[weeks["week"] == wk]
            if not row.empty:
                sd = row.iloc[0].get("start_date", None)
                ed = row.iloc[0].get("end_date", None)
                if pd.notna(sd) and pd.notna(ed):
                    st.markdown(f"<div class='small-note'>Dates: {sd} — {ed}</div>", unsafe_allow_html=True)

    wk_chal = chal[chal["week"] == wk].copy() if "week" in chal.columns else chal.copy()
    if wk_chal.empty:
        st.info("No challenges found for this week yet.")
    else:
        # Safe join to display winner team names if winner_team_id present
        if "winner_team_id" in wk_chal.columns and "team_id" in teams.columns:
            try:
                wk_chal = wk_chal.merge(
                    teams[["team_id", "team_name"]],
                    left_on="winner_team_id", right_on="team_id", how="left"
                )
            except Exception:
                # Fallback: show without names
                wk_chal["team_name"] = None

        cols = [c for c in ["challenge_name", "description", "prize_amount",
                            "team_name", "winner_details", "paid"] if c in wk_chal.columns]
        show = wk_chal[cols].rename(columns={
            "challenge_name": "Challenge",
            "description": "Description",
            "prize_amount": "Prize",
            "team_name": "Winner",
            "winner_details": "Details",
            "paid": "Paid"
        }).sort_values("Challenge")
        st.dataframe(show, use_container_width=True, height=400)

# ---------------- Survivor ----------------
with tab2:
    st.subheader("Survivor")
    if "eliminated_week" not in teams.columns:
        st.info("Add an 'eliminated_week' column to Teams (blank = still alive). Optional: eliminated_score, eliminated_note.")
    else:
        alive = teams[teams["eliminated_week"].isna()].copy().sort_values("team_name")
        st.markdown(f"**Still Alive ({len(alive)})**")
        cols_alive = [c for c in ["team_name", "owner"] if c in alive.columns]
        st.dataframe(alive[cols_alive], use_container_width=True, height=260)

        out = teams.dropna(subset=["eliminated_week"]).copy()
        if not out.empty:
            out["eliminated_week"] = out["eliminated_week"].astype(int)
            elim_cols = ["eliminated_week", "team_name"]
            for c in ["eliminated_score", "eliminated_note"]:
                if c in out.columns:
                    elim_cols.append(c)
            st.markdown("**Eliminations by Week**")
            st.dataframe(out.sort_values(["eliminated_week", "team_name"])[elim_cols],
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
        if awarded.empty:
            st.info("No winners recorded yet.")
        else:
            # Ensure ID alignment
            awarded["winner_team_id"] = _to_int_nullable(awarded["winner_team_id"])

            # Totals (awarded)
            by_team = awarded.groupby("winner_team_id", as_index=False)["prize_amount"].sum() \
                .rename(columns={"winner_team_id": "team_id", "prize_amount": "Awarded"})

            # Totals (paid) if paid column present/used
            if "paid" in awarded.columns:
                paid_totals = awarded[awarded["paid"]].groupby("winner_team_id", as_index=False)["prize_amount"].sum() \
                    .rename(columns={"winner_team_id": "team_id", "prize_amount": "Paid"})
                by_team = by_team.merge(paid_totals, on="team_id", how="left")
                by_team["Paid"] = by_team["Paid"].fillna(0)
            else:
                by_team["Paid"] = 0

            # Join team names & owners
            by_team = by_team.merge(teams[["team_id", "team_name", "owner"]], on="team_id", how="left") \
                             .sort_values(["Awarded", "team_name"], ascending=[False, True])

            st.dataframe(by_team[["team_name", "owner", "Awarded", "Paid"]],
                         use_container_width=True, height=420)

            # Season totals
            st.markdown("**Season Totals**")
            st.write(f"- **Total Awarded:** ${by_team['Awarded'].sum():,.0f}")
            st.write(f"- **Total Paid:** ${by_team['Paid'].sum():,.0f}")