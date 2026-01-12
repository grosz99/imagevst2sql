"""
CBBpy data service - fetches NCAA basketball data.
"""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import cbbpy.mens_scraper as cbb
import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Season constraints
SEASON_START = date(2025, 9, 1)
SEASON_END = date(2026, 1, 9)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "ncaa_basketball.db"


class CBBDataService:
    """Service for fetching and storing NCAA basketball data."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_score INTEGER,
                away_score INTEGER,
                game_date TEXT NOT NULL,
                venue TEXT,
                attendance INTEGER,
                fetched_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS boxscores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                team TEXT NOT NULL,
                player TEXT NOT NULL,
                player_id TEXT,
                position TEXT,
                starter INTEGER,
                minutes INTEGER,
                points INTEGER,
                rebounds INTEGER,
                assists INTEGER,
                steals INTEGER,
                blocks INTEGER,
                turnovers INTEGER,
                fgm INTEGER,
                fga INTEGER,
                fg3m INTEGER,
                fg3a INTEGER,
                ftm INTEGER,
                fta INTEGER,
                FOREIGN KEY (game_id) REFERENCES games(game_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT NOT NULL,
                games_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_points INTEGER DEFAULT 0,
                total_rebounds INTEGER DEFAULT 0,
                total_assists INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_boxscores_game ON boxscores(game_id)"
        )

        conn.commit()
        conn.close()
        logger.info("Database initialized", db_path=str(self.db_path))

    def fetch_games_for_date(self, game_date: str) -> list[str]:
        """Fetch game IDs for a specific date."""
        logger.info("Fetching games", date=game_date)
        game_ids = cbb.get_game_ids(game_date)
        return game_ids if game_ids else []

    def fetch_and_store_game(self, game_id: str) -> bool:
        """Fetch game info and boxscore, store in SQLite."""
        try:
            # Get game info
            info_df = cbb.get_game_info(game_id)
            if info_df is None or info_df.empty:
                logger.warning("No game info found", game_id=game_id)
                return False

            # Get boxscore
            box_df = cbb.get_game_boxscore(game_id)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Extract game data from info DataFrame
            row = info_df.iloc[0]
            cursor.execute("""
                INSERT OR REPLACE INTO games
                (game_id, home_team, away_team, home_score, away_score,
                 game_date, venue, attendance, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                str(row.get('home_team', '')),
                str(row.get('away_team', '')),
                int(row.get('home_score', 0)) if pd.notna(row.get('home_score')) else None,
                int(row.get('away_score', 0)) if pd.notna(row.get('away_score')) else None,
                str(row.get('game_date', '')),
                str(row.get('venue', '')) if pd.notna(row.get('venue')) else None,
                int(row.get('attendance', 0)) if pd.notna(row.get('attendance')) else None,
                datetime.utcnow().isoformat()
            ))

            # Store boxscore data
            if box_df is not None and not box_df.empty:
                cursor.execute("DELETE FROM boxscores WHERE game_id = ?", (game_id,))

                for _, player in box_df.iterrows():
                    cursor.execute("""
                        INSERT INTO boxscores
                        (game_id, team, player, player_id, position, starter,
                         minutes, points, rebounds, assists, steals, blocks,
                         turnovers, fgm, fga, fg3m, fg3a, ftm, fta)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game_id,
                        str(player.get('team', '')),
                        str(player.get('player', '')),
                        str(player.get('player_id', '')) if pd.notna(player.get('player_id')) else None,
                        str(player.get('position', '')) if pd.notna(player.get('position')) else None,
                        1 if player.get('starter') else 0,
                        int(player.get('min', 0)) if pd.notna(player.get('min')) else 0,
                        int(player.get('pts', 0)) if pd.notna(player.get('pts')) else 0,
                        int(player.get('reb', 0)) if pd.notna(player.get('reb')) else 0,
                        int(player.get('ast', 0)) if pd.notna(player.get('ast')) else 0,
                        int(player.get('stl', 0)) if pd.notna(player.get('stl')) else 0,
                        int(player.get('blk', 0)) if pd.notna(player.get('blk')) else 0,
                        int(player.get('to', 0)) if pd.notna(player.get('to')) else 0,
                        int(player.get('fgm', 0)) if pd.notna(player.get('fgm')) else 0,
                        int(player.get('fga', 0)) if pd.notna(player.get('fga')) else 0,
                        int(player.get('3pm', 0)) if pd.notna(player.get('3pm')) else 0,
                        int(player.get('3pa', 0)) if pd.notna(player.get('3pa')) else 0,
                        int(player.get('ftm', 0)) if pd.notna(player.get('ftm')) else 0,
                        int(player.get('fta', 0)) if pd.notna(player.get('fta')) else 0,
                    ))

            conn.commit()
            conn.close()
            logger.info("Game stored", game_id=game_id)
            return True

        except Exception as e:
            logger.error("Failed to fetch game", game_id=game_id, error=str(e))
            raise

    def load_date_range(self, start_date: str, end_date: str) -> int:
        """Load all games in a date range. Returns count of games loaded."""
        logger.info("Loading date range", start=start_date, end=end_date)

        game_ids = cbb.get_game_ids(start_date)
        if not game_ids:
            return 0

        loaded = 0
        for game_id in game_ids:
            try:
                if self.fetch_and_store_game(game_id):
                    loaded += 1
            except Exception as e:
                logger.warning("Skipping game", game_id=game_id, error=str(e))
                continue

        logger.info("Date range loaded", games_loaded=loaded)
        return loaded

    def get_team_standings(self) -> pd.DataFrame:
        """Get team standings from stored data."""
        conn = sqlite3.connect(self.db_path)
        query = """
            SELECT
                team,
                COUNT(*) as games_played,
                SUM(CASE WHEN is_winner = 1 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN is_winner = 0 THEN 1 ELSE 0 END) as losses,
                ROUND(AVG(points), 1) as ppg,
                ROUND(AVG(rebounds), 1) as rpg,
                ROUND(AVG(assists), 1) as apg
            FROM (
                SELECT
                    g.home_team as team,
                    g.home_score as points,
                    CASE WHEN g.home_score > g.away_score THEN 1 ELSE 0 END as is_winner,
                    (SELECT SUM(rebounds) FROM boxscores b WHERE b.game_id = g.game_id AND b.team = g.home_team) as rebounds,
                    (SELECT SUM(assists) FROM boxscores b WHERE b.game_id = g.game_id AND b.team = g.home_team) as assists
                FROM games g
                UNION ALL
                SELECT
                    g.away_team as team,
                    g.away_score as points,
                    CASE WHEN g.away_score > g.home_score THEN 1 ELSE 0 END as is_winner,
                    (SELECT SUM(rebounds) FROM boxscores b WHERE b.game_id = g.game_id AND b.team = g.away_team) as rebounds,
                    (SELECT SUM(assists) FROM boxscores b WHERE b.game_id = g.game_id AND b.team = g.away_team) as assists
                FROM games g
            )
            GROUP BY team
            ORDER BY wins DESC, ppg DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_recent_games(self, limit: int = 10) -> pd.DataFrame:
        """Get recent games."""
        conn = sqlite3.connect(self.db_path)
        query = f"""
            SELECT game_id, home_team, away_team, home_score, away_score, game_date
            FROM games
            ORDER BY game_date DESC
            LIMIT {limit}
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_top_scorers(self, limit: int = 10) -> pd.DataFrame:
        """Get top scorers across all games."""
        conn = sqlite3.connect(self.db_path)
        query = f"""
            SELECT
                player,
                team,
                COUNT(*) as games,
                SUM(points) as total_points,
                ROUND(AVG(points), 1) as ppg,
                ROUND(AVG(rebounds), 1) as rpg,
                ROUND(AVG(assists), 1) as apg
            FROM boxscores
            WHERE player != 'TEAM'
            GROUP BY player, team
            HAVING games >= 1
            ORDER BY ppg DESC
            LIMIT {limit}
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_game_count(self) -> int:
        """Get total number of games in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM games")
        count = cursor.fetchone()[0]
        conn.close()
        return count


if __name__ == "__main__":
    # Quick test
    service = CBBDataService()
    print(f"Database: {service.db_path}")
    print(f"Games in DB: {service.get_game_count()}")
