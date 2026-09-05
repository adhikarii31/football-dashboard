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

st.title("⚽ Match Analytics Dashboard")

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

    shot_data = []
    for team_df, team_name in ((team1_df, team1_name), (team2_df, team2_name)):
        shots = team_df[team_df["type"] == "Shot"].copy()
        if shots.empty:
            continue
        shots["minute_decimal"] = event_minutes(shots)
        xg_values = shots["shot_statsbomb_xg"] if "shot_statsbomb_xg" in shots else pd.Series(0, index=shots.index)
        shots["xg"] = pd.to_numeric(xg_values, errors="coerce").fillna(0)
        shot_data.append((team_name, shots))

    timeline = np.arange(0, 96, 1)
    cumulative_xg = {}
    for team_name, shots in shot_data:
        values = [shots.loc[shots["minute_decimal"] <= minute, "xg"].sum() for minute in timeline]
        cumulative_xg[team_name] = np.asarray(values)
        ax_xg.plot(timeline, values, linewidth=2, label=team_name)

    if cumulative_xg:
        ax_xg.legend(loc="upper left")
        ax_xg.set_ylabel("Cumulative xG")
        ax_xg.set_title("Cumulative Expected Goals")
        ax_xg.grid(alpha=0.25)

        team_values = list(cumulative_xg.values())
        momentum = team_values[0] - team_values[1] if len(team_values) == 2 else team_values[0]
        ax_momentum.bar(timeline, momentum, color=np.where(momentum >= 0, "#2166ac", "#b2182b"), width=0.9)
        ax_momentum.axhline(0, color="black", linewidth=0.8)
        ax_momentum.set_ylabel("xG advantage")
        ax_momentum.set_xlabel("Match minute")
        ax_momentum.set_title(f"Momentum ({team1_name} positive, {team2_name} negative)")
        ax_momentum.grid(axis="y", alpha=0.25)
    else:
        ax_xg.text(0.5, 0.5, "No shot data available", ha="center", va="center")
        ax_momentum.axis("off")

    fig.tight_layout()
    return fig


def create_pressure_heatmap(team_df, team_name, ax):
    pitch = VerticalPitch(pitch_type="statsbomb", pitch_color="white", line_color="black")
    pitch.draw(ax=ax)
    pressures = team_df[(team_df["type"] == "Pressure") & team_df["location"].notna()]
    if pressures.empty:
        ax.text(0.5, 0.5, "No pressure data available", transform=ax.transAxes, ha="center", va="center")
        ax.set_title(f"{team_name} Defensive Pressure")
        return

    locations = pressures["location"].tolist()
    x_values = [location[0] for location in locations if len(location) >= 2]
    y_values = [location[1] for location in locations if len(location) >= 2]
    if not x_values:
        ax.text(0.5, 0.5, "No pressure locations available", transform=ax.transAxes, ha="center", va="center")
        return

    stats = pitch.bin_statistic(x_values, y_values, statistic="count", bins=(6, 4))
    pitch.heatmap(stats, ax=ax, cmap="Reds", edgecolors="black", lw=0.2, alpha=0.8)
    ax.set_title(f"{team_name} Defensive Pressure")


def get_key_passes(team_df):
    passes = team_df[team_df["type"] == "Pass"].copy()
    if passes.empty or "player" not in passes:
        return pd.Series(dtype="int64")

    key_pass_mask = pd.Series(False, index=passes.index)
    for column in ("pass_assisted_shot_id", "pass_goal_assist"):
        if column in passes:
            values = passes[column]
            key_pass_mask |= values.notna() & (values.astype(str).str.lower() != "false")
    return passes.loc[key_pass_mask, "player"].dropna().value_counts()


def create_key_pass_chart(team1_df, team2_df, team1_name, team2_name):
    creators = pd.concat(
        [get_key_passes(team1_df).rename(team1_name), get_key_passes(team2_df).rename(team2_name)],
        axis=1,
    ).fillna(0)
    creators["Total"] = creators.sum(axis=1)
    creators = creators.sort_values("Total", ascending=True).tail(10)
    fig, ax = plt.subplots(figsize=(12, 5))
    if creators.empty:
        ax.text(0.5, 0.5, "No key pass data available", ha="center", va="center")
        ax.axis("off")
    else:
        creators[[team1_name, team2_name]].plot.barh(ax=ax, color=["#2166ac", "#b2182b"])
        ax.set_xlabel("Key passes")
        ax.set_ylabel("")
        ax.set_title("Top Key Pass Creators")
        ax.legend(title="Team")
        ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    return fig

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
    table = pd.DataFrame(data, columns=["Metric", "Team 1", "Team 2"])
    table[["Team 1", "Team 2"]] = table[["Team 1", "Team 2"]].astype(str)
    return table

# ---------------------------------------------------------
# SIDEBAR CONTROLS
# ---------------------------------------------------------

st.sidebar.title("Match Selector")

try:
    comps = get_competitions()
except Exception as exc:
    st.error(f"Unable to load competition data from StatsBomb: {exc}")
    st.stop()

if comps.empty:
    st.warning("StatsBomb returned no competitions.")
    st.stop()

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

    st.subheader("Game Momentum & xG Timeline")
    st.pyplot(create_momentum_xg(team1_df, team2_df, team1_name, team2_name))

    st.subheader("Tactical Networks & Shot Maps")
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

    st.subheader("Defensive Pressure Heatmaps")
    pressure_fig = plt.figure(figsize=(15, 6), facecolor="white")
    pressure_ax1 = pressure_fig.add_axes([0.05, 0.08, 0.4, 0.82], facecolor="white")
    pressure_ax2 = pressure_fig.add_axes([0.55, 0.08, 0.4, 0.82], facecolor="white")
    create_pressure_heatmap(team1_df, team1_name, pressure_ax1)
    create_pressure_heatmap(team2_df, team2_name, pressure_ax2)
    st.pyplot(pressure_fig)

    st.subheader("Top Key Pass Creators")
    st.pyplot(create_key_pass_chart(team1_df, team2_df, team1_name, team2_name))
else:
    st.warning("Insufficient event data available for this match.")
