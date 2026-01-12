"""
NCAA Basketball Boxscore Dashboard
Displays game boxscores in ESPN-style layout with game selector.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "data" / "ncaa_basketball.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


@st.cache_data(ttl=60)
def get_games():
    """Get all games for selector."""
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT game_id, game_date, status,
               home_team_name, home_team_abbrev, home_team_score, home_team_rank,
               away_team_name, away_team_abbrev, away_team_score, away_team_rank
        FROM games
        ORDER BY game_date DESC
    """, conn)
    conn.close()
    return df


@st.cache_data(ttl=60)
def get_boxscore(game_id: str):
    """Get boxscore data for a game."""
    conn = get_connection()

    # Game info
    game = pd.read_sql_query(
        "SELECT * FROM games WHERE game_id = ?",
        conn, params=(game_id,)
    ).iloc[0]

    # Players
    players = pd.read_sql_query("""
        SELECT * FROM players WHERE game_id = ?
        ORDER BY is_home DESC, starter DESC, minutes DESC
    """, conn, params=(game_id,))

    conn.close()
    return game, players


def format_shooting(made, attempted):
    """Format shooting stats like '5-10'."""
    return f"{made}-{attempted}"


def render_player_table(players_df: pd.DataFrame, team_name: str):
    """Render a player stats table matching ESPN style."""

    # Separate starters and bench
    starters = players_df[players_df['starter'] == 1].copy()
    bench = players_df[players_df['starter'] == 0].copy()

    def format_player_row(p):
        name = p['player_name']
        jersey = f"#{p['jersey']}" if p['jersey'] else ""
        return f"{name} {jersey}"

    # Build display dataframe
    def build_table(df, header):
        if df.empty:
            return None

        display_df = pd.DataFrame({
            header: df.apply(format_player_row, axis=1),
            'MIN': df['minutes'],
            'PTS': df['points'],
            'FG': df.apply(lambda r: format_shooting(r['fg_made'], r['fg_attempted']), axis=1),
            '3PT': df.apply(lambda r: format_shooting(r['fg3_made'], r['fg3_attempted']), axis=1),
            'FT': df.apply(lambda r: format_shooting(r['ft_made'], r['ft_attempted']), axis=1),
            'REB': df['rebounds'],
            'AST': df['assists'],
            'TO': df['turnovers'],
            'STL': df['steals'],
            'BLK': df['blocks'],
            'OREB': df['offensive_rebounds'],
            'DREB': df['defensive_rebounds'],
            'PF': df['fouls']
        })
        return display_df

    starters_table = build_table(starters, 'STARTERS')
    bench_table = build_table(bench, 'BENCH')

    # Team totals
    totals = {
        'MIN': players_df['minutes'].sum(),
        'PTS': players_df['points'].sum(),
        'FG': format_shooting(players_df['fg_made'].sum(), players_df['fg_attempted'].sum()),
        '3PT': format_shooting(players_df['fg3_made'].sum(), players_df['fg3_attempted'].sum()),
        'FT': format_shooting(players_df['ft_made'].sum(), players_df['ft_attempted'].sum()),
        'REB': players_df['rebounds'].sum(),
        'AST': players_df['assists'].sum(),
        'TO': players_df['turnovers'].sum(),
        'STL': players_df['steals'].sum(),
        'BLK': players_df['blocks'].sum(),
        'OREB': players_df['offensive_rebounds'].sum(),
        'DREB': players_df['defensive_rebounds'].sum(),
        'PF': players_df['fouls'].sum()
    }

    # Calculate percentages
    fg_pct = (players_df['fg_made'].sum() / players_df['fg_attempted'].sum() * 100
              if players_df['fg_attempted'].sum() > 0 else 0)
    fg3_pct = (players_df['fg3_made'].sum() / players_df['fg3_attempted'].sum() * 100
               if players_df['fg3_attempted'].sum() > 0 else 0)
    ft_pct = (players_df['ft_made'].sum() / players_df['ft_attempted'].sum() * 100
              if players_df['ft_attempted'].sum() > 0 else 0)

    return starters_table, bench_table, totals, (fg_pct, fg3_pct, ft_pct)


def main():
    st.set_page_config(
        page_title="NCAA Basketball Boxscores",
        page_icon="🏀",
        layout="wide"
    )

    # Custom CSS for ESPN-like styling
    st.markdown("""
    <style>
    .team-header {
        font-size: 1.5em;
        font-weight: bold;
        padding: 10px;
        margin-bottom: 10px;
    }
    .score-box {
        font-size: 3em;
        font-weight: bold;
        text-align: center;
    }
    .team-record {
        font-size: 0.8em;
        color: #666;
    }
    .team-rank {
        font-size: 0.9em;
        color: #999;
    }
    div[data-testid="stDataFrame"] {
        font-size: 12px;
    }
    .totals-row {
        font-weight: bold;
        background-color: #f0f0f0;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("🏀 NCAA Basketball Boxscores")

    # Load games
    games_df = get_games()

    if games_df.empty:
        st.error("No games found in database. Run load_espn_data.py first.")
        return

    # Game selector
    game_options = []
    for _, g in games_df.iterrows():
        away_rank = f"#{int(g['away_team_rank'])} " if pd.notna(g['away_team_rank']) else ""
        home_rank = f"#{int(g['home_team_rank'])} " if pd.notna(g['home_team_rank']) else ""
        label = f"{away_rank}{g['away_team_abbrev']} {g['away_team_score']} @ {home_rank}{g['home_team_abbrev']} {g['home_team_score']} ({g['game_date'][:10]})"
        game_options.append((g['game_id'], label))

    selected_idx = st.selectbox(
        "Select Game",
        range(len(game_options)),
        format_func=lambda i: game_options[i][1]
    )

    selected_game_id = game_options[selected_idx][0]

    # Load boxscore
    game, players = get_boxscore(selected_game_id)

    # Header with scores
    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        away_rank = f"#{int(game['away_team_rank'])} " if pd.notna(game['away_team_rank']) else ""
        st.markdown(f"### {away_rank}{game['away_team_name']}")
        st.markdown(f"<div class='score-box'>{game['away_team_score']}</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div style='text-align:center; font-size:2em; padding-top:30px;'>@</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div style='text-align:center; color:#666;'>{game['status']}</div>",
                    unsafe_allow_html=True)

    with col3:
        home_rank = f"#{int(game['home_team_rank'])} " if pd.notna(game['home_team_rank']) else ""
        st.markdown(f"### {home_rank}{game['home_team_name']}")
        st.markdown(f"<div class='score-box'>{game['home_team_score']}</div>", unsafe_allow_html=True)

    st.divider()

    # Split players by team
    away_players = players[players['is_home'] == 0]
    home_players = players[players['is_home'] == 1]

    # Side by side layout - Away on left, Home on right
    left_col, right_col = st.columns(2)

    # Away team boxscore (LEFT)
    with left_col:
        st.markdown(f"### {game['away_team_name']}")
        away_starters, away_bench, away_totals, away_pcts = render_player_table(
            away_players, game['away_team_name']
        )

        if away_starters is not None:
            st.dataframe(away_starters, use_container_width=True, hide_index=True)

        if away_bench is not None and not away_bench.empty:
            st.dataframe(away_bench, use_container_width=True, hide_index=True)

        # Team totals
        totals_df = pd.DataFrame([{
            'TEAM': 'TOTALS',
            'PTS': away_totals['PTS'],
            'FG': away_totals['FG'],
            '3PT': away_totals['3PT'],
            'FT': away_totals['FT'],
            'REB': away_totals['REB'],
            'AST': away_totals['AST'],
        }])
        st.dataframe(totals_df, use_container_width=True, hide_index=True)
        st.caption(f"FG: {away_pcts[0]:.0f}% | 3PT: {away_pcts[1]:.0f}% | FT: {away_pcts[2]:.0f}%")

    # Home team boxscore (RIGHT)
    with right_col:
        st.markdown(f"### {game['home_team_name']}")
        home_starters, home_bench, home_totals, home_pcts = render_player_table(
            home_players, game['home_team_name']
        )

        if home_starters is not None:
            st.dataframe(home_starters, use_container_width=True, hide_index=True)

        if home_bench is not None and not home_bench.empty:
            st.dataframe(home_bench, use_container_width=True, hide_index=True)

        # Team totals
        totals_df = pd.DataFrame([{
            'TEAM': 'TOTALS',
            'PTS': home_totals['PTS'],
            'FG': home_totals['FG'],
            '3PT': home_totals['3PT'],
            'FT': home_totals['FT'],
            'REB': home_totals['REB'],
            'AST': home_totals['AST'],
        }])
        st.dataframe(totals_df, use_container_width=True, hide_index=True)
        st.caption(f"FG: {home_pcts[0]:.0f}% | 3PT: {home_pcts[1]:.0f}% | FT: {home_pcts[2]:.0f}%")


if __name__ == "__main__":
    main()
