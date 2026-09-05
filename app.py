import subprocess
import sys

# Function to auto-install packages if missing
def install_package(package):
    try:
        __import__(package)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Force-install missing libraries at startup
install_package("matplotlib")
install_package("mplsoccer")
install_package("statsbombpy")
install_package("pandas")
install_package("numpy")

# Now load your standard imports safely
import matplotlib.pyplot as plt
import streamlit as st
import pandas as pd
import numpy as np
import mplsoccer
# ... rest of your code ...import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from statsbombpy import sb
from mplsoccer import VerticalPitch

# Page setup
st.set_page_config(layout="wide", page_title="Football Match Analytics Dashboard")

# Force explicit styling to prevent dark mode/black screen rendering issues
st.markdown("""
    <style>
    .stApp {
        background-color: #FFFFFF;
        color: #000000;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# DATA FETCHING & CACHING (Dynamic Match Selection)
# ---------------------------------------------------------

@st.cache_data
def get_competitions():
    return sb.competitions()

@st.cache_data
def get_matches(comp_id, season_id):
    return sb.matches(competition_id=comp_id, season_id=season_id)

@st.cache_data
def load_match_data(match_id):
    df = sb.events(match_id=match_id).sort_values(by="index")
    df = df[df["period"] < 5]  # Exclude penalty shootout for standard view
    return df

# ---------------------------------------------------------
# VISUALIZATION FUNCTIONS
# ---------------------------------------------------------

def create_shotmap(team_df, ax):
    pitch = VerticalPitch(pitch_type='statsbomb', half=True, pitch_color='white', line_color='black')
    pitch.draw(ax=ax)
    shots = team_df[team_df['type'] == 'Shot'].copy()
    if not shots.empty:
        for _, shot in shots.iterrows():
            x = shot['location'][0]
            y = shot['location'][1]
            xg = shot.get('shot_statsbomb_xg', 0.1)
            is_goal = shot.get('shot_outcome') == 'Goal'
            color = 'red' if is_goal else 'blue'
            ax.scatter(y, x, s=max(xg * 400, 30), c=color, alpha=0.6, edgecolors='black', zorder=3)

def create_pass_network(team_df, ax):
    pitch = VerticalPitch(pitch_type='statsbomb', pitch_color='white', line_color='black')
    pitch.draw(ax=ax)
    passes = team_df[(team_df['type'] == 'Pass') & (team_df['pass_outcome'].isna())].copy()
    if not passes.empty:
        # Group by passer to find average locations
        passers = passes.groupby('player').agg({
            'location': lambda locs: (
                sum(l[0] for l in locs) / len(locs),
                sum(l[1] for l in locs) / len(locs)
            ), 
            'id': 'count'
        }).reset_index()
        
        for _, passer in passers.iterrows():
            ax.scatter(passer['location'][1], passer['location'][0], s=passer['id'] * 8 + 20, c='red', edgecolors='black', zorder=3)

def create_table(team1_df, team2_df):
    def get_xg(df):
        shots = df[df['type'] == 'Shot']
        return round(shots['shot_statsbomb_xg'].sum(), 2) if 'shot_statsbomb_xg' in shots else 0.0

    def get_passes(df):
        passes = df[df['type'] == 'Pass']
        acc = passes[passes['pass_outcome'].isna()]
        pct = round((len(acc) / len(passes) * 100), 1) if len(passes) > 0 else 0
        return len(passes), pct

    t1_passes, t1_acc = get_passes(team1_df)
    t2_passes, t2_acc = get_passes(team2_df)

    data = [
        ["Expected Goals (xG)", get_xg(team1_df), get_xg(team2_df)],
        ["Shots", len(team1_df[team1_df['type'] == 'Shot']), len(team2_df[team2_df['type'] == 'Shot'])],
        ["Passes", t1_passes, t2_passes],
        ["Pass Completion %", f"{t1_acc}%", f"{t2_acc}%"]
    ]
    return pd.DataFrame(data, columns=["Metric", "Team 1", "Team 2"])

# ---------------------------------------------------------
# SIDEBAR CONTROLS
# ---------------------------------------------------------

st.sidebar.title("Match Selector")

comps = get_competitions()
comp_names = comps['competition_name'].unique()
selected_comp = st.sidebar.selectbox("Select Competition", comp_names)

filtered_seasons = comps[comps['competition_name'] == selected_comp]
season_names = filtered_seasons['season_name'].unique()
selected_season = st.sidebar.selectbox("Select Season", season_names)

comp_id = filtered_seasons[filtered_seasons['season_name'] == selected_season]['competition_id'].values[0]
season_id = filtered_seasons[filtered_seasons['season_name'] == selected_season]['season_id'].values[0]

matches = get_matches(comp_id, season_id)
match_dict = {f"{m['home_team']} vs {m['away_team']} ({m['match_date']})": m['match_id'] for _, m in matches.iterrows()}
selected_match_label = st.sidebar.selectbox("Select Match", list(match_dict.keys()))

match_id = match_dict[selected_match_label]

# ---------------------------------------------------------
# MAIN DASHBOARD INTERFACE
# ---------------------------------------------------------

st.title("⚽ Match Analytics Dashboard")

with st.spinner("Fetching event data from StatsBomb..."):
    df = load_match_data(match_id)

teams = df['team'].dropna().unique()

if len(teams) >= 2:
    team1_name, team2_name = teams[0], teams[1]
    team1_df = df[df['team'] == team1_name]
    team2_df = df[df['team'] == team2_name]

    st.header(f"{team1_name} vs {team2_name}")

    st.subheader("Match Summary")
    stats_df = create_table(team1_df, team2_df)
    stats_df.columns = ["Metric", team1_name, team2_name]
    st.table(stats_df)

    # Figure container with explicit white facecolors
    fig = plt.figure(figsize=(15, 12), facecolor='white')
    
    ax_pass1 = fig.add_axes([0.05, 0.52, 0.4, 0.4], facecolor='white')
    ax_pass2 = fig.add_axes([0.55, 0.52, 0.4, 0.4], facecolor='white')
    ax_shot1 = fig.add_axes([0.05, 0.05, 0.4, 0.4], facecolor='white')
    ax_shot2 = fig.add_axes([0.55, 0.05, 0.4, 0.4], facecolor='white')

    ax_pass1.set_title(f"{team1_name} Pass Network", fontsize=14, color='black')
    create_pass_network(team1_df, ax_pass1)

    ax_pass2.set_title(f"{team2_name} Pass Network", fontsize=14, color='black')
    create_pass_network(team2_df, ax_pass2)

    ax_shot1.set_title(f"{team1_name} Shot Map", fontsize=14, color='black')
    create_shotmap(team1_df, ax_shot1)

    ax_shot2.set_title(f"{team2_name} Shot Map", fontsize=14, color='black')
    create_shotmap(team2_df, ax_shot2)

    st.pyplot(fig)
else:
    st.warning("Insufficient event data available for this match.")
