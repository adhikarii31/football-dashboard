import streamlit as st
import pandas as pd
import numpy as np
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


def create_momentum_xg(team1_df, team2_df, team1_name, team2_name):
    fig, (ax_xg, ax_momentum) = plt.subplots(
        2, 1, figsize=(14, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
    )

    def event_minutes(team_df):
        minutes = team_df["minute"].fillna(0).astype(float)
        seconds = team_df["second"].fillna(0).astype(float) if "second" in team_df else 0
        return minutes + seconds / 60
