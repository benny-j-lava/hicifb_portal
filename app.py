import streamlit as st
import pandas as pd
from datetime import datetime, date

# ------------------ CONFIG: REPLACE THESE ------------------
CSV_TEAMS       = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=0&single=true&output=csv"
CSV_WEEKS       = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=29563283&single=true&output=csv"
CSV_CHALLENGES  = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=570391343&single=true&output=csv"
LEAGUE_TITLE    = "🏈 HICIFB 2025 League Portal"
# -----------------------------------------------------------

st.set_page_config(page_title="League Portal", layout="wide", initial_sidebar_state="collapsed")

# ------------------ Helpers ------------------
def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df

def to_int_nullable(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")

def to_bool_loose(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin(["y", "yes", "true", "1"])

def parse_date_col(df: pd.DataFrame, colname: str) -> None:
    if colname in df.columns:
        df[colname] = pd.to_datetime(df[colname], errors="coerce")  # -> datetime64[ns]

def ensure_week_columns(weeks: pd.DataFrame) -> pd.DataFrame:
    # Map common alternate headers to start_date / end_date if needed
    alt_map = {
        "start": "start_date", "startdate": "start_date",
        "end": "end_date", "enddate": "end_date",
    }
    for src, dst in alt_map.items():
        if src in weeks.columns and dst not in weeks.columns:
            weeks[dst] = weeks[src]
    return weeks

def get_current_week(weeks: pd.DataFrame) -> int | None:
    if weeks.empty or "start_date" not in weeks or "end_date" not in weeks or "week" not in weeks:
        return None
    # today as Timestamp for clean comparison with datetime64 series
    today_ts = pd.Timestamp(datetime.now().date())
    mask = (weeks["start_date"] <= today_ts) & (today_ts <= weeks["end_date"])
    hit = weeks[mask]
    if not hit.empty and pd.notna(hit.iloc[0]["week"]):
        return int(hit.iloc[0]["week"])
    # fallback: latest started week
    past = weeks[(weeks["start_date"] <= today_ts) & weeks["week"].notna()].sort_values("start_date")
    if not past.empty:
        return int(past.iloc[-1]["week"])
    # final fallback: earliest week available
    wk = weeks.loc[weeks["week"].notna(), "week"]
    return int(wk.min()) if not wk.empty else None

def fmt_money(x):
    try:
        return f"${float(x):,.0f}"
    except Exception:
        return x

# ------------------ Data Load ------------------
@st.cache_data(ttl=300)
def load_data():
    teams = norm_cols(pd.read_csv(CSV_TEAMS))
    weeks = norm_cols(pd.read_csv(CSV_WEEKS))
    chal  = norm_cols(pd.read_csv(CSV_CHALLENGES))

    # Parse weeks dates robustly
    weeks = ensure_week_columns(weeks)
    parse_date_col(weeks, "start_date")
    parse_date_col(weeks, "end_date")
    if "week" in weeks:
        weeks["week"] = to_int_nullable(weeks["week"])

    # IDs & numeric fields
    if "team_id" in teams:
        teams["team_id"] = to_int_nullable(teams["team_id"])
    if "eliminated_week" in teams:
        teams["eliminated_week"] = to_int_nullable(teams["eliminated_week"])

    if "winner_team_id" in chal:
        chal["winner_team_id"] = to_int_nullable(chal["winner_team_id"])
    if "week" in chal:
        chal["week"] = to_int_nullable(chal["week"])
    if "prize_amount" in chal:
        chal["prize_amount"] = pd.to_numeric(chal["prize_amount"], errors="coerce").fillna(0)

    # Paid flag (optional)
    if "paid" in chal:
        chal["paid"] = to_bool_loose(chal["paid"])
    else:
        chal["paid"] = False

    return teams, weeks, chal

try:
    teams, weeks, chal = load_data()
except Exception as e:
    st.error("Failed to load data. Check your CSV URLs and that each tab is published as CSV.")
    st.exception(e)
    st.stop()

# Compute current week with fallbacks
wk_current = get_current_week(weeks)
if wk_current is None:
    # fallback to max week in challenges if weeks parsing didn’t work
    wk_current = int(chal["week"].dropna().max()) if "week" in chal.columns and not chal.empty else 1

# ------------------ Header ------------------
st.title(LEAGUE_TITLE)

# Show date range if available
date_line = ""
if not weeks.empty and {"week", "start_date", "end_date"}.issubset(weeks.columns):
    row = weeks.loc[weeks["week"] == wk_current]
    if not row.empty:
        sd = row.iloc[0]["start_date"]
        ed = row.iloc[0]["end_date"]
        if pd.notna(sd) and pd.notna(ed):
            date_line = f" — {sd.date()} to {ed.date()}"
st.caption(f"Week {wk_current}{date_line}")

# ------------------ Section 1: This Week’s Challenges ------------------
st.subheader("📌 This Week’s Challenges")

wk_chal = chal[chal["week"] == wk_current].copy() if "week" in chal.columns else chal.copy()
# Try to join winner name
if not wk_chal.empty and "winner_team_id" in wk_chal.columns and "team_id" in teams.columns:
    try:
        wk_chal = wk_chal.merge(teams[["team_id", "team_name"]], left_on="winner_team_id", right_on="team_id", how="left")
    except Exception:
        wk_chal["team_name"] = None

if wk_chal.empty:
    st.info("No challenges found for this week yet.")
else:
    # Render as compact cards
    for _, r in wk_chal.sort_values("challenge_name").iterrows():
        with st.container():
            left, mid, right = st.columns([3, 1, 2])
            with left:
                st.markdown(f"**{r.get('challenge_name','Challenge')}**")
                if pd.notna(r.get("description")):
                    st.caption(r["description"])
            with mid:
                st.metric("Prize", fmt_money(r.get("prize_amount", 0)))
            with right:
                winner = r.get("team_name")
                details = r.get("winner_details", "")
                paid = bool(r.get("paid", False))
                if pd.notna(winner):
                    st.write(f"🏆 **{winner}**")
                    if isinstance(details, str) and details.strip():
                        st.caption(details)
                if paid:
                    st.success("Paid")

st.markdown("---")

# ------------------ Section 2: Challenge Winners History ------------------
st.subheader("📜 Challenge Winners History")

hist = chal.copy()
if "winner_team_id" in hist.columns and "team_id" in teams.columns:
    try:
        hist = hist.merge(teams[["team_id", "team_name"]], left_on="winner_team_id", right_on="team_id", how="left")
    except Exception:
        hist["team_name"] = None

cols = [c for c in ["week", "challenge_name", "team_name", "prize_amount", "paid"] if c in hist.columns]
hist_show = hist[cols].rename(columns={
    "week": "Week",
    "challenge_name": "Challenge",
    "team_name": "Winner",
    "prize_amount": "Prize",
    "paid": "Paid",
}).sort_values(["Week", "Challenge"])

# Pretty money
if "Prize" in hist_show.columns:
    hist_show["Prize"] = hist_show["Prize"].apply(fmt_money)

st.dataframe(hist_show, use_container_width=True, height=420)

st.markdown("---")

# ------------------ Section 3: Payouts by Team (Totals) ------------------
st.subheader("🏆 Payouts by Team")

awarded = chal.dropna(subset=["winner_team_id"]).copy() if "winner_team_id" in chal else pd.DataFrame()
if awarded.empty:
    st.info("No winners recorded yet.")
else:
    awarded["winner_team_id"] = to_int_nullable(awarded["winner_team_id"])
    by_team = awarded.groupby("winner_team_id", as_index=False)["prize_amount"].sum() \
        .rename(columns={"winner_team_id": "team_id", "prize_amount": "Total_Won"})

    # Paid totals (optional)
    if "paid" in awarded.columns:
        paid_totals = awarded[awarded["paid"]].groupby("winner_team_id", as_index=False)["prize_amount"].sum() \
            .rename(columns={"winner_team_id": "team_id", "prize_amount": "Total_Paid"})
        by_team = by_team.merge(paid_totals, on="team_id", how="left")
        by_team["Total_Paid"] = by_team["Total_Paid"].fillna(0)
    else:
        by_team["Total_Paid"] = 0

    by_team = by_team.merge(teams[["team_id", "team_name", "owner"]], on="team_id", how="left") \
                     .sort_values(["Total_Won", "team_name"], ascending=[False, True])

    show_cols = ["team_name", "owner", "Total_Won", "Total_Paid"]
    # Pretty money
    for mcol in ["Total_Won", "Total_Paid"]:
        if mcol in by_team.columns:
            by_team[mcol] = by_team[mcol].apply(fmt_money)

    st.dataframe(by_team[show_cols], use_container_width=True, height=420)

    # Season totals
    raw_tot_won = awarded["prize_amount"].sum()
    raw_tot_paid = awarded.loc[awarded.get("paid", False), "prize_amount"].sum() if "paid" in awarded.columns else 0
    st.markdown("**Season Totals**")
    st.write(f"- **Total Awarded:** {fmt_money(raw_tot_won)}")
    st.write(f"- **Total Paid:** {fmt_money(raw_tot_paid)}")

st.markdown("---")

# ------------------ Survivor (from Teams.eliminated_week) ------------------
st.subheader("🪓 Survivor (Guillotine)")

if "eliminated_week" not in teams.columns:
    st.info("Add an 'eliminated_week' column to Teams (blank = still alive). Optional: eliminated_score, eliminated_note.")
else:
    alive = teams[teams["eliminated_week"].isna()].copy().sort_values("team_name")
    st.markdown(f"**Still Alive ({len(alive)})**")
    st.dataframe(alive[[c for c in ["team_name", "owner"] if c in alive.columns]],
                 use_container_width=True, height=240)

    out = teams.dropna(subset=["eliminated_week"]).copy()
    if out.empty:
        st.caption("_No eliminations recorded yet._")
    else:
        out["eliminated_week"] = out["eliminated_week"].astype(int)
        elim_cols = ["eliminated_week", "team_name"]
        for c in ["eliminated_score", "eliminated_note"]:
            if c in out.columns:
                elim_cols.append(c)
        st.markdown("**Eliminations by Week**")
        st.dataframe(out.sort_values(["eliminated_week", "team_name"])[elim_cols],
                     use_container_width=True, height=320)

# ------------------ Optional: tiny debug toggle ------------------
with st.expander("🔧 Debug (types)"):
    st.write("Weeks dtypes:", dict(weeks.dtypes))
    st.write("Challenges dtypes:", dict(chal.dtypes))
    st.write("Teams dtypes:", dict(teams.dtypes))