import streamlit as st
import pandas as pd
from datetime import datetime, date

# ------------------ CONFIG: REPLACE THESE ------------------
CSV_TEAMS       = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=0&single=true&output=csv"
CSV_WEEKS       = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=29563283&single=true&output=csv"
CSV_CHALLENGES  = "https://docs.google.com/spreadsheets/d/e/2PACX-1vToS6-KCa5gBhrUPLevOIlcFlt4PFQkmnnC7tyCQDc3r145W3xB23ggq55NNF663qFdu4WIJ05LGHki/pub?gid=570391343&single=true&output=csv"
# -----------------------------------------------------------

st.set_page_config(page_title="Fantasy League Portal", layout="wide")

@st.cache_data(ttl=300)
def load():
    teams = pd.read_csv(CSV_TEAMS)
    weeks = pd.read_csv(CSV_WEEKS)
    chal  = pd.read_csv(CSV_CHALLENGES)

    # normalize
    for df in (teams, weeks, chal):
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # parse weeks
    if "start_date" in weeks: weeks["start_date"] = pd.to_datetime(weeks["start_date"])
    if "end_date" in weeks: weeks["end_date"] = pd.to_datetime(weeks["end_date"])

    chal["prize_amount"] = pd.to_numeric(chal["prize_amount"], errors="coerce").fillna(0)
    chal["winner_team_id"] = pd.to_numeric(chal.get("winner_team_id", pd.Series([])), errors="coerce")

    return teams, weeks, chal

teams, weeks, chal = load()

# -------- Current week --------
today = datetime.now().date()
wk_row = weeks[(weeks["start_date"] <= today) & (today <= weeks["end_date"])]
wk = int(wk_row.iloc[0]["week"]) if not wk_row.empty else int(chal["week"].max())

st.title("🏈 HICIFB 2025 League Portal")
st.caption(f"Week {wk} — {weeks.loc[weeks['week']==wk,'start_date'].iloc[0].date()} to {weeks.loc[weeks['week']==wk,'end_date'].iloc[0].date()}")

# ===== Section 1: This Week's Challenges =====
st.subheader("📌 This Week’s Challenges")
wk_chal = chal[chal["week"] == wk].copy()

if "winner_team_id" in wk_chal.columns:
    wk_chal = wk_chal.merge(teams[["team_id","team_name"]], left_on="winner_team_id", right_on="team_id", how="left")

for _, row in wk_chal.iterrows():
    with st.container():
        st.markdown(f"**{row['challenge_name']}** — {row['description']}")
        st.write(f"💰 Prize: ${row['prize_amount']}")
        if pd.notna(row.get("team_name")):
            st.write(f"🏆 Winner: {row['team_name']} ({row.get('winner_details','')})")
        if row.get("paid", False):
            st.write("✅ Paid")

st.markdown("---")

# ===== Section 2: Challenge History =====
st.subheader("📜 Challenge Winners History")

chal_hist = chal.copy()
if "winner_team_id" in chal_hist.columns:
    chal_hist = chal_hist.merge(teams[["team_id","team_name"]], left_on="winner_team_id", right_on="team_id", how="left")

cols = [c for c in ["week","challenge_name","team_name","prize_amount","paid"] if c in chal_hist.columns]
chal_hist = chal_hist[cols].rename(columns={
    "week":"Week", "challenge_name":"Challenge", "team_name":"Winner",
    "prize_amount":"Prize", "paid":"Paid"
}).sort_values(["Week","Challenge"])

st.dataframe(chal_hist, use_container_width=True, height=400)

st.markdown("---")

# ===== Section 3: Team Standings =====
st.subheader("🏆 Payouts by Team")

awarded = chal.dropna(subset=["winner_team_id"]).copy()
by_team = awarded.groupby("winner_team_id", as_index=False)["prize_amount"].sum()
by_team = by_team.rename(columns={"winner_team_id":"team_id","prize_amount":"Total_Won"})
by_team = by_team.merge(teams[["team_id","team_name","owner"]], on="team_id", how="left")
by_team = by_team.sort_values("Total_Won", ascending=False)

st.dataframe(by_team[["team_name","owner","Total_Won"]], use_container_width=True, height=400)