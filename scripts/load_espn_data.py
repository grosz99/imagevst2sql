"""
Load NCAA basketball data from ESPN into SQLite.
Time range: Nov 4, 2025 (season start) to Jan 10, 2026
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cbbscrapter import ESPNCollegeBasketball, NoGamesFoundError

DB_PATH = Path(__file__).parent.parent / "data" / "ncaa_basketball.db"


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            game_date TEXT NOT NULL,
            status TEXT,
            home_team_id TEXT,
            home_team_name TEXT,
            home_team_abbrev TEXT,
            home_team_score INTEGER,
            home_team_rank INTEGER,
            home_team_record TEXT,
            away_team_id TEXT,
            away_team_name TEXT,
            away_team_abbrev TEXT,
            away_team_score INTEGER,
            away_team_rank INTEGER,
            away_team_record TEXT,
            venue TEXT,
            attendance INTEGER,
            fetched_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            team_id TEXT NOT NULL,
            team_name TEXT,
            is_home INTEGER,
            player_id TEXT,
            player_name TEXT,
            jersey TEXT,
            position TEXT,
            starter INTEGER,
            minutes INTEGER,
            points INTEGER,
            rebounds INTEGER,
            assists INTEGER,
            steals INTEGER,
            blocks INTEGER,
            turnovers INTEGER,
            fouls INTEGER,
            fg_made INTEGER,
            fg_attempted INTEGER,
            fg3_made INTEGER,
            fg3_attempted INTEGER,
            ft_made INTEGER,
            ft_attempted INTEGER,
            offensive_rebounds INTEGER,
            defensive_rebounds INTEGER,
            FOREIGN KEY (game_id) REFERENCES games(game_id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_game ON players(game_id)")

    conn.commit()
    return conn


def store_boxscore(conn: sqlite3.Connection, box) -> None:
    """Store a boxscore in the database."""
    cursor = conn.cursor()

    # Store game info
    cursor.execute("""
        INSERT OR REPLACE INTO games
        (game_id, game_date, status, home_team_id, home_team_name, home_team_abbrev,
         home_team_score, home_team_rank, home_team_record, away_team_id, away_team_name,
         away_team_abbrev, away_team_score, away_team_rank, away_team_record, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        box.game_id,
        box.game_date.isoformat(),
        box.status,
        box.home_team.id,
        box.home_team.display_name,
        box.home_team.abbreviation,
        box.home_team.score,
        box.home_team.rank,
        box.home_team.record,
        box.away_team.id,
        box.away_team.display_name,
        box.away_team.abbreviation,
        box.away_team.score,
        box.away_team.rank,
        box.away_team.record,
        datetime.utcnow().isoformat()
    ))

    # Delete existing players for this game
    cursor.execute("DELETE FROM players WHERE game_id = ?", (box.game_id,))

    # Store home players
    for p in box.home_players:
        cursor.execute("""
            INSERT INTO players
            (game_id, team_id, team_name, is_home, player_id, player_name, jersey,
             position, starter, minutes, points, rebounds, assists, steals, blocks,
             turnovers, fouls, fg_made, fg_attempted, fg3_made, fg3_attempted,
             ft_made, ft_attempted, offensive_rebounds, defensive_rebounds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            box.game_id, box.home_team.id, box.home_team.display_name, 1,
            p.player_id, p.name, p.jersey, p.position, 1 if p.starter else 0,
            p.minutes, p.points, p.rebounds, p.assists, p.steals, p.blocks,
            p.turnovers, p.fouls, p.fg_made, p.fg_attempted, p.fg3_made,
            p.fg3_attempted, p.ft_made, p.ft_attempted, p.offensive_rebounds,
            p.defensive_rebounds
        ))

    # Store away players
    for p in box.away_players:
        cursor.execute("""
            INSERT INTO players
            (game_id, team_id, team_name, is_home, player_id, player_name, jersey,
             position, starter, minutes, points, rebounds, assists, steals, blocks,
             turnovers, fouls, fg_made, fg_attempted, fg3_made, fg3_attempted,
             ft_made, ft_attempted, offensive_rebounds, defensive_rebounds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            box.game_id, box.away_team.id, box.away_team.display_name, 0,
            p.player_id, p.name, p.jersey, p.position, 1 if p.starter else 0,
            p.minutes, p.points, p.rebounds, p.assists, p.steals, p.blocks,
            p.turnovers, p.fouls, p.fg_made, p.fg_attempted, p.fg3_made,
            p.fg3_attempted, p.ft_made, p.ft_attempted, p.offensive_rebounds,
            p.defensive_rebounds
        ))

    conn.commit()


def load_date(scraper: ESPNCollegeBasketball, conn: sqlite3.Connection, date_str: str) -> int:
    """Load all games for a date. Returns count loaded."""
    try:
        games = scraper.get_games_for_date(date_str)
    except NoGamesFoundError:
        return 0

    loaded = 0
    for game in games:
        # Only load final games
        if "FINAL" not in game.status.upper():
            continue

        try:
            box = scraper.get_boxscore(game.game_id)
            store_boxscore(conn, box)
            loaded += 1
            print(f"    {game.game_id}: {game.short_name}")
        except Exception as e:
            print(f"    [ERROR] {game.game_id}: {e}")

    return loaded


def main():
    print("=" * 60)
    print("NCAA Basketball Data Loader")
    print("=" * 60)

    # Initialize
    conn = init_db(DB_PATH)
    scraper = ESPNCollegeBasketball()

    # Check existing data
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM games")
    existing = cursor.fetchone()[0]
    print(f"Database: {DB_PATH}")
    print(f"Existing games: {existing}")

    # Load recent games (Jan 8-10, 2026 for quick test)
    print("\nLoading games from Jan 8-10, 2026...")

    total_loaded = 0
    for date in ["2026-01-08", "2026-01-09", "2026-01-10"]:
        print(f"\n{date}:")
        loaded = load_date(scraper, conn, date)
        total_loaded += loaded
        print(f"  Loaded {loaded} games")

    print(f"\n{'=' * 60}")
    print(f"Total games loaded: {total_loaded}")

    # Show summary
    cursor.execute("SELECT COUNT(*) FROM games")
    total_games = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM players")
    total_players = cursor.fetchone()[0]

    print(f"Database now has: {total_games} games, {total_players} player records")

    conn.close()


if __name__ == "__main__":
    main()
