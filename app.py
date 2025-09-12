# app.py
import streamlit as st
import pandas as pd
from datetime import datetime

# ------------------ YOUR LINKS ------------------
CSV_TEAMS       = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=0&single=true&output=csv"
CSV_WEEKS       = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=29563283&single=true&output=csv"
CSV_CHALLENGES  = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=570391343&single=true&output=csv"
LEAGUE_TITLE    = "🏈 HICIFB 2025 League Portal"
LEAGUE_FEE      = 100  # per-team buy-in used for Net earnings
# ------------------------------------------------

st.set_page_config(page_title="League Portal", layout="wide", initial_sidebar_state="collapsed")

# ------------------ helpers ------------------
def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df

def parse_date(df: pd.DataFrame, col: str):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

def ensure_week_headers(weeks: pd.DataFrame) -> pd.DataFrame:
    # map common alternates -> start_date/end_date
    alt = {"start": "start_date", "startdate": "start_date", "end": "end_date", "enddate": "end_date"}
    for src, dst in alt.items():
        if src in weeks.columns and dst not in weeks.columns:
            weeks[dst] = weeks[src]
    return weeks

def norm_id_series(s: pd.Series) -> pd.Series:
    # keep IDs like "t9" as strings; blank -> NaN
    out = s.astype(str).str.strip().str.lower()
    return out.mask(out.isin(["", "nan", "none"]))

def to_bool_loose(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin(["y", "yes", "true", "1"])

def current_week_from_calendar(weeks: pd.DataFrame) -> int | None:
    if weeks.empty or not {"week", "start_date", "end_date"}.issubset(weeks.columns):
        return None
    today_ts = pd.Timestamp(datetime.now().date())
    hit = weeks[(weeks["start_date"] <= today_ts) & (today_ts <= weeks["end_date"])]
    if not hit.empty and pd.notna(hit.iloc[0]["week"]):
        return int(hit.iloc[0]["week"])
    past = weeks[(weeks["start_date"] <= today_ts) & weeks["week"].notna()].sort_values("start_date")
    if not past.empty:
        return int(past.iloc[-1]["week"])
    w = weeks["week"].dropna()
    return int(w.min()) if not w.empty else None

def money(x):
    try:
        return f"${float(x):,.0f}"
    except Exception:
        return x

# ------------------ data load ------------------
@st.cache_data(ttl=300)
def load():
    teams = norm_cols(pd.read_csv(CSV_TEAMS))
    weeks = norm_cols(pd.read_csv(CSV_WEEKS))
    chal  = norm_cols(pd.read_csv(CSV_CHALLENGES))

    # handle "prize amount" -> prize_amount
    if "prize amount" in chal.columns and "prize_amount" not in chal.columns:
        chal.rename(columns={"prize amount": "prize_amount"}, inplace=True)

    # parse dates / weeks
    weeks = ensure_week_headers(weeks)
    parse_date(weeks, "start_date")
    parse_date(weeks, "end_date")
    if "week" in weeks: weeks["week"] = pd.to_numeric(weeks["week"], errors="coerce").astype("Int64")
    if "week" in chal:  chal["week"]  = pd.to_numeric(chal["week"],  errors="coerce").astype("Int64")

    # IDs as strings (t1, t2, …)
    if "team_id" in teams:       teams["team_id"] = norm_id_series(teams["team_id"])
    if "winner_team_id" in chal: chal["winner_team_id"] = norm_id_series(chal["winner_team_id"])

    # survivor column mapping from your Teams sheet
    # your columns: team_id, team_name, owner, notes, survivor_eliminated_week, still_alive
    if "survivor_eliminated_week" in teams.columns and "eliminated_week" not in teams.columns:
        teams["eliminated_week"] = pd.to_numeric(teams["survivor_eliminated_week"], errors="coerce").astype("Int64")
    elif "eliminated_week" in teams.columns:
        teams["eliminated_week"] = pd.to_numeric(teams["eliminated_week"], errors="coerce").astype("Int64")

    # numeric money & paid flag
    if "prize_amount" in chal: chal["prize_amount"] = pd.to_numeric(chal["prize_amount"], errors="coerce").fillna(0.0)
    if "paid" in chal:         chal["paid"] = to_bool_loose(chal["paid"])
    else:                      chal["paid"] = False

    return teams, weeks, chal

try:
    teams, weeks, chal = load()
except Exception as e:
    st.error("Failed to load data. Check your CSV links and that each tab is published as CSV.")
    st.exception(e)
    st.stop()

wk_current = current_week_from_calendar(weeks)
if wk_current is None:
    wk_current = int(chal["week"].dropna().max()) if "week" in chal.columns and not chal.empty else 1

# ------------------ header ------------------
st.title(LEAGUE_TITLE)

date_line = ""
if not weeks.empty and {"week","start_date","end_date"}.issubset(weeks.columns):
    row = weeks.loc[weeks["week"] == wk_current]
    if not row.empty:
        sd, ed = row.iloc[0]["start_date"], row.iloc[0]["end_date"]
        if pd.notna(sd) and pd.notna(ed):
            date_line = f" — {sd.date()} to {ed.date()}"
st.caption(f"Week {wk_current}{date_line}")

# toggle to include future weeks
show_future = st.checkbox("Include future weeks", value=False)
MAX_WEEK = int(wk_current or 1)

# ------------------ this week ------------------
st.subheader("📌 This Week’s Challenges")

wk = st.number_input(
    "Week",
    min_value=1,
    max_value=(999 if show_future else MAX_WEEK),
    value=min(int(wk_current or 1), MAX_WEEK),
    step=1,
)

wk_chal = chal[chal["week"] == wk].copy() if "week" in chal.columns else chal.copy()

# join winner names
if not wk_chal.empty and {"winner_team_id"}.issubset(wk_chal.columns) and "team_id" in teams.columns:
    try:
        wk_chal = wk_chal.merge(teams[["team_id","team_name"]], left_on="winner_team_id", right_on="team_id", how="left")
    except Exception:
        wk_chal["team_name"] = None

if wk_chal.empty:
    st.info("No challenges found for this week yet.")
else:
    # de-dupe within a week by challenge_id (or challenge_name if desired)
    if "challenge_id" in wk_chal.columns:
        wk_chal["has_winner"] = wk_chal["winner_team_id"].notna()
        wk_chal = wk_chal.sort_values(["has_winner","paid","challenge_id"], ascending=[False, False, True]) \
                         .drop_duplicates(subset=["challenge_id"], keep="first")
    for _, r in wk_chal.sort_values("challenge_name").iterrows():
        with st.container():
            left, mid, right = st.columns([3,1,2])
            with left:
                st.markdown(f"**{r.get('challenge_name','Challenge')}**")
                desc = r.get("description")
                if isinstance(desc, str) and desc.strip():
                    st.caption(desc)
            with mid:
                st.metric("Prize", money(r.get("prize_amount", 0)))
            with right:
                winner = r.get("team_name")
                details = r.get("winner_details", "")
                if isinstance(winner, str) and winner.strip():
                    st.write(f"🏆 **{winner}**")
                    if isinstance(details, str) and details.strip():
                        st.caption(details)
                if bool(r.get("paid", False)):
                    st.success("Paid")

st.markdown("---")

# ------------------ history ------------------
st.subheader("📜 Challenge Winners History")

hist = chal.copy()
if "week" in hist.columns and not show_future:
    hist = hist[hist["week"].notna()]
    hist = hist[hist["week"] <= MAX_WEEK]

if "winner_team_id" in hist.columns and "team_id" in teams.columns:
    try:
        hist = hist.merge(teams[["team_id","team_name"]], left_on="winner_team_id", right_on="team_id", how="left")
    except Exception:
        hist["team_name"] = None

# drop ID from view
cols = [c for c in ["week","challenge_name","team_name","prize_amount","paid"] if c in hist.columns]
hist_show = hist[cols].rename(columns={
    "week":"Week",
    "challenge_name":"Challenge",
    "team_name":"Winner",
    "prize_amount":"Prize",
    "paid":"Paid"
})

# --- make "High Score" sort first within each week ---
hist_show["__prio"] = (hist_show["Challenge"].astype(str).str.strip().str.lower() != "high score").astype(int)
hist_show = hist_show.sort_values(["Week", "__prio", "Challenge"]).drop(columns="__prio")

if "Prize" in hist_show.columns:
    hist_show["Prize"] = hist_show["Prize"].apply(money)

st.dataframe(hist_show, use_container_width=True, height=420, hide_index=True)

st.markdown("---")

# ------------------ payouts by team (with Net) ------------------
st.subheader("🏆 Payouts by Team")

awarded = chal.dropna(subset=["winner_team_id"]).copy() if "winner_team_id" in chal else pd.DataFrame()
if not awarded.empty and "week" in awarded.columns and not show_future:
    awarded = awarded[awarded["week"].notna()]
    awarded = awarded[awarded["week"] <= MAX_WEEK]

if awarded.empty:
    st.info("No winners recorded yet.")
else:
    # numeric totals
    totals_won = awarded.groupby("winner_team_id", as_index=False)["prize_amount"].sum() \
                        .rename(columns={"winner_team_id":"team_id","prize_amount":"Total_Won"})
    if "paid" in awarded.columns:
        totals_paid = awarded[awarded["paid"]].groupby("winner_team_id", as_index=False)["prize_amount"].sum() \
                        .rename(columns={"winner_team_id":"team_id","prize_amount":"Total_Paid"})
    else:
        totals_paid = pd.DataFrame({"team_id": [], "Total_Paid": []})

    by_team = totals_won.merge(totals_paid, on="team_id", how="left").fillna({"Total_Paid": 0.0})
    by_team = by_team.merge(teams[["team_id","team_name","owner"]], on="team_id", how="left")

    # league fee + nets
    by_team["Fee"]          = float(LEAGUE_FEE)
    by_team["Net_Awarded"]  = by_team["Total_Won"]  - by_team["Fee"]
    by_team["Net_Paid"]     = by_team["Total_Paid"] - by_team["Fee"]

    by_team = by_team.sort_values(["Total_Won","team_name"], ascending=[False, True])

    # toggle which net to color/emphasize
    use_paid_for_net = st.toggle("Calculate Net using Paid (vs Awarded)", value=True)
    net_col = "Net_Paid" if use_paid_for_net else "Net_Awarded"

    disp = by_team[["team_name","owner","Total_Won","Total_Paid","Fee","Net_Awarded","Net_Paid"]].copy()

    # styling
    def color_net(s):
        return ["color: green;" if v > 0 else "color: red;" if v < 0 else "" for v in s]

    styled = (disp.style
              .format({c: money for c in ["Total_Won","Total_Paid","Fee","Net_Awarded","Net_Paid"]})
              .apply(color_net, subset=[net_col]))

    st.dataframe(styled, use_container_width=True, height=460, hide_index=True)

    # season totals (raw)
    raw_tot_won  = float(awarded["prize_amount"].sum())
    raw_tot_paid = float(awarded.loc[awarded.get("paid", False), "prize_amount"].sum()) if "paid" in awarded.columns else 0.0
    st.markdown("**Season Totals**")
    st.write(f"- **Total Awarded:** {money(raw_tot_won)}")
    st.write(f"- **Total Paid:** {money(raw_tot_paid)}")

st.markdown("---")

# ------------------ survivor (from Teams) ------------------
st.subheader("🪓 Survivor (Guillotine)")
if "eliminated_week" not in teams.columns:
    st.info("Add an 'eliminated_week' column to Teams (blank = still alive). Optional: eliminated_score, eliminated_note.")
else:
    alive = teams[teams["eliminated_week"].isna()].copy().sort_values("team_name")
    st.markdown(f"**Still Alive ({len(alive)})**")
    st.dataframe(
        alive[[c for c in ["team_name","owner"] if c in alive.columns]],
        use_container_width=True, height=240, hide_index=True
    )

    out = teams.dropna(subset=["eliminated_week"]).copy()
    if out.empty:
        st.caption("_No eliminations recorded yet._")
    else:
        out["eliminated_week"] = out["eliminated_week"].astype(int)
        if not show_future:
            out = out[out["eliminated_week"] <= MAX_WEEK]
        elim_cols = ["eliminated_week","team_name"]
        for c in ["eliminated_score","eliminated_note"]:
            if c in out.columns: elim_cols.append(c)
        st.markdown("**Eliminations by Week**")
        st.dataframe(
            out.sort_values(["eliminated_week","team_name"])[elim_cols],
            use_container_width=True, height=320, hide_index=True
        )

# ------------------ debug (optional) ------------------
with st.expander("🔧 Debug (types)"):
    st.write("Weeks dtypes:", dict(weeks.dtypes))
    st.write("Challenges dtypes:", dict(chal.dtypes))
    st.write("Teams dtypes:", dict(teams.dtypes))