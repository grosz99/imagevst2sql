# src/services/espn_cbb_scraper.py
"""
ESPN College Basketball Scraper

A lightweight scraper for NCAA basketball data from ESPN's public API.
No external package dependencies beyond requests/httpx and pydantic.

FOLLOWS CLAUDE.MD RULES:
- All data returned as Pydantic models (no raw dicts)
- No fake data fallbacks (raises exceptions on errors)
- Proper error handling with typed exceptions
- Security: No sensitive data logging

Usage:
    scraper = ESPNCollegeBasketball()
    
    # Get games for a date
    games = scraper.get_games_for_date("2025-11-15")
    
    # Get boxscore
    boxscore = scraper.get_boxscore("401812788")
    
    # Get play-by-play
    pbp = scraper.get_play_by_play("401812788")
"""

import requests
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# =============================================================================
# EXCEPTIONS (No fake data - fail explicitly)
# =============================================================================

class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass


class GameNotFoundError(ScraperError):
    """Raised when a game ID doesn't exist."""
    pass


class NoGamesFoundError(ScraperError):
    """Raised when no games exist for a date."""
    pass


class APIError(ScraperError):
    """Raised when ESPN API returns an error."""
    pass


# =============================================================================
# PYDANTIC MODELS (All structured data flows through these)
# =============================================================================

class GameStatus(str, Enum):
    """Game status enum."""
    SCHEDULED = "STATUS_SCHEDULED"
    IN_PROGRESS = "STATUS_IN_PROGRESS"
    FINAL = "STATUS_FINAL"
    POSTPONED = "STATUS_POSTPONED"
    CANCELED = "STATUS_CANCELED"


class Team(BaseModel):
    """Team information."""
    id: str
    name: str
    abbreviation: str
    display_name: str
    logo_url: Optional[str] = None
    rank: Optional[int] = None
    record: Optional[str] = None
    score: Optional[int] = None
    
    model_config = {"extra": "ignore"}


class GameSummary(BaseModel):
    """Summary of a single game."""
    game_id: str
    date: datetime
    name: str
    short_name: str
    status: str
    home_team: Team
    away_team: Team
    venue: Optional[str] = None
    attendance: Optional[int] = None
    
    @property
    def is_final(self) -> bool:
        return "FINAL" in self.status.upper()
    
    model_config = {"extra": "ignore"}


class PlayerStats(BaseModel):
    """Individual player statistics."""
    player_id: str
    name: str
    jersey: Optional[str] = None
    position: Optional[str] = None
    starter: bool = False
    
    # Stats
    minutes: int = 0
    points: int = 0
    rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    fouls: int = 0
    
    # Shooting
    fg_made: int = 0
    fg_attempted: int = 0
    fg3_made: int = 0
    fg3_attempted: int = 0
    ft_made: int = 0
    ft_attempted: int = 0
    
    # Rebounds breakdown
    offensive_rebounds: int = 0
    defensive_rebounds: int = 0
    
    @property
    def fg_pct(self) -> float:
        return self.fg_made / self.fg_attempted if self.fg_attempted > 0 else 0.0
    
    @property
    def fg3_pct(self) -> float:
        return self.fg3_made / self.fg3_attempted if self.fg3_attempted > 0 else 0.0
    
    @property
    def ft_pct(self) -> float:
        return self.ft_made / self.ft_attempted if self.ft_attempted > 0 else 0.0
    
    model_config = {"extra": "ignore"}


class TeamStats(BaseModel):
    """Team-level statistics."""
    team_id: str
    team_name: str
    
    # Shooting
    fg_made: int = 0
    fg_attempted: int = 0
    fg_pct: float = 0.0
    fg3_made: int = 0
    fg3_attempted: int = 0
    fg3_pct: float = 0.0
    ft_made: int = 0
    ft_attempted: int = 0
    ft_pct: float = 0.0
    
    # Other
    rebounds: int = 0
    offensive_rebounds: int = 0
    defensive_rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    fouls: int = 0
    points_in_paint: int = 0
    fast_break_points: int = 0
    points_off_turnovers: int = 0
    largest_lead: int = 0
    
    model_config = {"extra": "ignore"}


class BoxScore(BaseModel):
    """Complete boxscore for a game."""
    game_id: str
    game_date: datetime
    status: str
    
    home_team: Team
    away_team: Team
    
    home_players: list[PlayerStats] = Field(default_factory=list)
    away_players: list[PlayerStats] = Field(default_factory=list)
    
    home_stats: Optional[TeamStats] = None
    away_stats: Optional[TeamStats] = None
    
    @property
    def is_final(self) -> bool:
        return "FINAL" in self.status.upper()
    
    model_config = {"extra": "ignore"}


class Play(BaseModel):
    """Single play from play-by-play."""
    play_id: str
    sequence_number: int
    period: int
    clock: str
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    description: str
    score_home: int = 0
    score_away: int = 0
    scoring_play: bool = False
    
    model_config = {"extra": "ignore"}


class PlayByPlay(BaseModel):
    """Complete play-by-play for a game."""
    game_id: str
    home_team: Team
    away_team: Team
    plays: list[Play] = Field(default_factory=list)
    
    @property
    def total_plays(self) -> int:
        return len(self.plays)
    
    def get_plays_by_period(self, period: int) -> list[Play]:
        """Get all plays for a specific period."""
        return [p for p in self.plays if p.period == period]
    
    def get_scoring_plays(self) -> list[Play]:
        """Get only scoring plays."""
        return [p for p in self.plays if p.scoring_play]
    
    model_config = {"extra": "ignore"}


# =============================================================================
# MAIN SCRAPER CLASS
# =============================================================================

class ESPNCollegeBasketball:
    """
    ESPN College Basketball Scraper.
    
    Scrapes data from ESPN's public API endpoints.
    All methods return validated Pydantic models.
    
    Example:
        scraper = ESPNCollegeBasketball()
        games = scraper.get_games_for_date("2025-11-15")
        boxscore = scraper.get_boxscore(games[0].game_id)
    """
    
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
    
    def __init__(self, timeout: int = 30):
        """
        Initialize scraper.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; CBBScraper/1.0)"
        })
    
    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Make GET request to ESPN API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response as dict
            
        Raises:
            APIError: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise APIError(f"ESPN API request failed: {e}")
    
    # =========================================================================
    # GAMES BY DATE
    # =========================================================================
    
    def get_games_for_date(self, game_date: str) -> list[GameSummary]:
        """
        Get all games for a specific date.
        
        Args:
            game_date: Date string in format "YYYY-MM-DD" or "YYYYMMDD"
            
        Returns:
            List of GameSummary models
            
        Raises:
            NoGamesFoundError: If no games on that date
            APIError: If API request fails
        """
        # Normalize date format
        clean_date = game_date.replace("-", "")
        
        data = self._get("scoreboard", params={"dates": clean_date})
        
        events = data.get("events", [])
        if not events:
            raise NoGamesFoundError(f"No games found for {game_date}")
        
        games = []
        for event in events:
            game = self._parse_game_summary(event)
            if game:
                games.append(game)
        
        return games
    
    def get_game_ids_for_date(self, game_date: str) -> list[str]:
        """
        Get just game IDs for a date (lightweight).
        
        Args:
            game_date: Date in "YYYY-MM-DD" or "YYYYMMDD" format
            
        Returns:
            List of game ID strings
        """
        games = self.get_games_for_date(game_date)
        return [g.game_id for g in games]
    
    def _parse_game_summary(self, event: dict) -> Optional[GameSummary]:
        """Parse event JSON into GameSummary model."""
        try:
            competitions = event.get("competitions", [{}])[0]
            competitors = competitions.get("competitors", [])
            
            home_data = next((c for c in competitors if c.get("homeAway") == "home"), {})
            away_data = next((c for c in competitors if c.get("homeAway") == "away"), {})
            
            venue = competitions.get("venue", {}).get("fullName")
            attendance = competitions.get("attendance")
            
            return GameSummary(
                game_id=event.get("id"),
                date=datetime.fromisoformat(event.get("date").replace("Z", "+00:00")),
                name=event.get("name", ""),
                short_name=event.get("shortName", ""),
                status=event.get("status", {}).get("type", {}).get("name", "UNKNOWN"),
                home_team=self._parse_team(home_data),
                away_team=self._parse_team(away_data),
                venue=venue,
                attendance=int(attendance) if attendance else None
            )
        except Exception:
            return None
    
    def _parse_team(self, team_data: dict) -> Team:
        """Parse team data from competitor JSON."""
        team_info = team_data.get("team", {})
        
        # Get rank if ranked
        rank = None
        if team_data.get("curatedRank", {}).get("current"):
            rank = team_data["curatedRank"]["current"]
        
        # Get record
        record = None
        records = team_data.get("records", [])
        if records:
            record = records[0].get("summary")
        
        return Team(
            id=team_info.get("id", ""),
            name=team_info.get("name", ""),
            abbreviation=team_info.get("abbreviation", ""),
            display_name=team_info.get("displayName", ""),
            logo_url=team_info.get("logo"),
            rank=rank,
            record=record,
            score=int(team_data.get("score", 0)) if team_data.get("score") else None
        )
    
    # =========================================================================
    # BOXSCORE
    # =========================================================================
    
    def get_boxscore(self, game_id: str) -> BoxScore:
        """
        Get complete boxscore for a game.
        
        Args:
            game_id: ESPN game ID
            
        Returns:
            BoxScore model with player and team stats
            
        Raises:
            GameNotFoundError: If game doesn't exist
            APIError: If API request fails
        """
        data = self._get("summary", params={"event": game_id})
        
        if not data:
            raise GameNotFoundError(f"Game {game_id} not found")
        
        return self._parse_boxscore(game_id, data)
    
    def _parse_boxscore(self, game_id: str, data: dict) -> BoxScore:
        """Parse summary JSON into BoxScore model."""
        
        # Get basic game info
        game_info = data.get("header", {}).get("competitions", [{}])[0]
        competitors = game_info.get("competitors", [])
        
        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})
        
        home_team = self._parse_team(home_comp)
        away_team = self._parse_team(away_comp)
        
        # Get player stats
        boxscore_data = data.get("boxscore", {})
        players_data = boxscore_data.get("players", [])
        
        home_players = []
        away_players = []
        
        for team_players in players_data:
            team_id = team_players.get("team", {}).get("id")
            statistics = team_players.get("statistics", [])
            
            if statistics:
                stat_block = statistics[0]  # Usually just one stat block
                athletes = stat_block.get("athletes", [])
                
                for athlete in athletes:
                    player_stats = self._parse_player_stats(athlete, stat_block.get("keys", []))
                    
                    if team_id == home_team.id:
                        home_players.append(player_stats)
                    else:
                        away_players.append(player_stats)
        
        # Get team stats
        teams_data = boxscore_data.get("teams", [])
        home_stats = None
        away_stats = None
        
        for team_stat_block in teams_data:
            team_id = team_stat_block.get("team", {}).get("id")
            stats = self._parse_team_stats(team_stat_block)
            
            if team_id == home_team.id:
                home_stats = stats
            else:
                away_stats = stats
        
        # Get game date and status
        game_date_str = data.get("header", {}).get("competitions", [{}])[0].get("date", "")
        status = data.get("header", {}).get("competitions", [{}])[0].get("status", {}).get("type", {}).get("name", "")
        
        return BoxScore(
            game_id=game_id,
            game_date=datetime.fromisoformat(game_date_str.replace("Z", "+00:00")) if game_date_str else datetime.now(),
            status=status,
            home_team=home_team,
            away_team=away_team,
            home_players=home_players,
            away_players=away_players,
            home_stats=home_stats,
            away_stats=away_stats
        )
    
    def _parse_player_stats(self, athlete: dict, keys: list[str]) -> PlayerStats:
        """Parse athlete JSON into PlayerStats model."""
        athlete_info = athlete.get("athlete", {})
        stats = athlete.get("stats", [])
        
        # Create a dict mapping stat keys to values
        stat_dict = {}
        for i, key in enumerate(keys):
            if i < len(stats):
                stat_dict[key] = stats[i]
        
        # Parse minutes - handle both "32" and "32:45" formats
        minutes = 0
        min_val = stat_dict.get("minutes") or stat_dict.get("min", "0")
        try:
            if ":" in str(min_val):
                minutes = int(str(min_val).split(":")[0])
            else:
                minutes = int(min_val)
        except (ValueError, AttributeError):
            pass

        # Parse shooting stats (format: "8-14")
        def parse_made_attempted(val: str) -> tuple[int, int]:
            try:
                parts = str(val).split("-")
                return int(parts[0]), int(parts[1])
            except (ValueError, IndexError, AttributeError):
                return 0, 0

        # Handle both key formats from ESPN API
        fg_key = "fieldGoalsMade-fieldGoalsAttempted" if "fieldGoalsMade-fieldGoalsAttempted" in stat_dict else "fg"
        fg3_key = "threePointFieldGoalsMade-threePointFieldGoalsAttempted" if "threePointFieldGoalsMade-threePointFieldGoalsAttempted" in stat_dict else "3pt"
        ft_key = "freeThrowsMade-freeThrowsAttempted" if "freeThrowsMade-freeThrowsAttempted" in stat_dict else "ft"

        fg_made, fg_attempted = parse_made_attempted(stat_dict.get(fg_key, "0-0"))
        fg3_made, fg3_attempted = parse_made_attempted(stat_dict.get(fg3_key, "0-0"))
        ft_made, ft_attempted = parse_made_attempted(stat_dict.get(ft_key, "0-0"))

        # Safe int parsing helper
        def safe_int(val) -> int:
            try:
                return int(val) if val else 0
            except (ValueError, TypeError):
                return 0

        return PlayerStats(
            player_id=athlete_info.get("id", ""),
            name=athlete_info.get("displayName", ""),
            jersey=athlete_info.get("jersey"),
            position=athlete_info.get("position", {}).get("abbreviation"),
            starter=athlete.get("starter", False),
            minutes=minutes,
            points=safe_int(stat_dict.get("points") or stat_dict.get("pts", 0)),
            rebounds=safe_int(stat_dict.get("rebounds") or stat_dict.get("reb", 0)),
            assists=safe_int(stat_dict.get("assists") or stat_dict.get("ast", 0)),
            steals=safe_int(stat_dict.get("steals") or stat_dict.get("stl", 0)),
            blocks=safe_int(stat_dict.get("blocks") or stat_dict.get("blk", 0)),
            turnovers=safe_int(stat_dict.get("turnovers") or stat_dict.get("to", 0)),
            fouls=safe_int(stat_dict.get("fouls") or stat_dict.get("pf", 0)),
            fg_made=fg_made,
            fg_attempted=fg_attempted,
            fg3_made=fg3_made,
            fg3_attempted=fg3_attempted,
            ft_made=ft_made,
            ft_attempted=ft_attempted,
            offensive_rebounds=safe_int(stat_dict.get("offensiveRebounds") or stat_dict.get("oreb", 0)),
            defensive_rebounds=safe_int(stat_dict.get("defensiveRebounds") or stat_dict.get("dreb", 0))
        )
    
    def _parse_team_stats(self, team_block: dict) -> TeamStats:
        """Parse team stats block into TeamStats model."""
        team_info = team_block.get("team", {})
        statistics = team_block.get("statistics", [])
        
        # Build stat dict
        stat_dict = {}
        for stat in statistics:
            stat_dict[stat.get("name", "")] = stat.get("displayValue", "0")
        
        def safe_int(val) -> int:
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return 0
        
        def safe_float(val) -> float:
            try:
                return float(val.replace("%", "")) / 100 if "%" in str(val) else float(val)
            except (ValueError, TypeError, AttributeError):
                return 0.0
        
        # Parse shooting (format: "29-59")
        def parse_shooting(val: str) -> tuple[int, int]:
            try:
                parts = val.split("-")
                return int(parts[0]), int(parts[1])
            except (ValueError, IndexError, AttributeError):
                return 0, 0
        
        fg_made, fg_attempted = parse_shooting(stat_dict.get("fieldGoalsMade-fieldGoalsAttempted", "0-0"))
        fg3_made, fg3_attempted = parse_shooting(stat_dict.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted", "0-0"))
        ft_made, ft_attempted = parse_shooting(stat_dict.get("freeThrowsMade-freeThrowsAttempted", "0-0"))
        
        return TeamStats(
            team_id=team_info.get("id", ""),
            team_name=team_info.get("displayName", ""),
            fg_made=fg_made,
            fg_attempted=fg_attempted,
            fg_pct=safe_float(stat_dict.get("fieldGoalPct", "0")),
            fg3_made=fg3_made,
            fg3_attempted=fg3_attempted,
            fg3_pct=safe_float(stat_dict.get("threePointFieldGoalPct", "0")),
            ft_made=ft_made,
            ft_attempted=ft_attempted,
            ft_pct=safe_float(stat_dict.get("freeThrowPct", "0")),
            rebounds=safe_int(stat_dict.get("totalRebounds", 0)),
            offensive_rebounds=safe_int(stat_dict.get("offensiveRebounds", 0)),
            defensive_rebounds=safe_int(stat_dict.get("defensiveRebounds", 0)),
            assists=safe_int(stat_dict.get("assists", 0)),
            steals=safe_int(stat_dict.get("steals", 0)),
            blocks=safe_int(stat_dict.get("blocks", 0)),
            turnovers=safe_int(stat_dict.get("totalTurnovers", 0)),
            fouls=safe_int(stat_dict.get("fouls", 0)),
            points_in_paint=safe_int(stat_dict.get("pointsInPaint", 0)),
            fast_break_points=safe_int(stat_dict.get("fastBreakPoints", 0)),
            points_off_turnovers=safe_int(stat_dict.get("turnoverPoints", 0)),
            largest_lead=safe_int(stat_dict.get("largestLead", 0))
        )
    
    # =========================================================================
    # PLAY-BY-PLAY
    # =========================================================================
    
    def get_play_by_play(self, game_id: str) -> PlayByPlay:
        """
        Get play-by-play data for a game.
        
        Args:
            game_id: ESPN game ID
            
        Returns:
            PlayByPlay model with all plays
            
        Raises:
            GameNotFoundError: If game doesn't exist
            APIError: If API request fails
        """
        data = self._get("summary", params={"event": game_id})
        
        if not data:
            raise GameNotFoundError(f"Game {game_id} not found")
        
        return self._parse_play_by_play(game_id, data)
    
    def _parse_play_by_play(self, game_id: str, data: dict) -> PlayByPlay:
        """Parse summary JSON into PlayByPlay model."""
        
        # Get teams
        game_info = data.get("header", {}).get("competitions", [{}])[0]
        competitors = game_info.get("competitors", [])
        
        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})
        
        home_team = self._parse_team(home_comp)
        away_team = self._parse_team(away_comp)
        
        # Get plays
        plays_data = data.get("plays", [])
        plays = []
        
        for i, play in enumerate(plays_data):
            parsed = self._parse_play(play, i, home_team, away_team)
            if parsed:
                plays.append(parsed)
        
        return PlayByPlay(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            plays=plays
        )
    
    def _parse_play(self, play: dict, sequence: int, home_team: Team, away_team: Team) -> Optional[Play]:
        """Parse play JSON into Play model."""
        try:
            team_id = play.get("team", {}).get("id")
            
            # Determine team name
            team_name = None
            if team_id == home_team.id:
                team_name = home_team.name
            elif team_id == away_team.id:
                team_name = away_team.name
            
            return Play(
                play_id=play.get("id", str(sequence)),
                sequence_number=sequence,
                period=play.get("period", {}).get("number", 1),
                clock=play.get("clock", {}).get("displayValue", ""),
                team_id=team_id,
                team_name=team_name,
                description=play.get("text", ""),
                score_home=play.get("homeScore", 0),
                score_away=play.get("awayScore", 0),
                scoring_play=play.get("scoringPlay", False)
            )
        except Exception:
            return None
    
    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================
    
    def get_game(
        self, 
        game_id: str, 
        include_boxscore: bool = True, 
        include_pbp: bool = False
    ) -> dict:
        """
        Get all data for a game in one call.
        
        Args:
            game_id: ESPN game ID
            include_boxscore: Include player/team stats
            include_pbp: Include play-by-play
            
        Returns:
            Dict with 'boxscore' and optionally 'pbp' keys
        """
        result = {}
        
        if include_boxscore:
            result["boxscore"] = self.get_boxscore(game_id)
        
        if include_pbp:
            result["pbp"] = self.get_play_by_play(game_id)
        
        return result
    
    def get_games_range(
        self, 
        start_date: str, 
        end_date: str, 
        include_boxscore: bool = False
    ) -> list[GameSummary]:
        """
        Get games across a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            include_boxscore: If True, fetches full boxscore for each game (slower)
            
        Returns:
            List of GameSummary objects
        """
        from datetime import timedelta
        
        start = datetime.strptime(start_date.replace("-", ""), "%Y%m%d")
        end = datetime.strptime(end_date.replace("-", ""), "%Y%m%d")
        
        all_games = []
        current = start
        
        while current <= end:
            date_str = current.strftime("%Y%m%d")
            try:
                games = self.get_games_for_date(date_str)
                all_games.extend(games)
            except NoGamesFoundError:
                pass  # Skip dates with no games
            
            current += timedelta(days=1)
        
        return all_games


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    scraper = ESPNCollegeBasketball()
    
    print("=" * 60)
    print("ESPN College Basketball Scraper Test")
    print("=" * 60)
    
    # Test 1: Get games for November 15, 2025
    print("\n[TEST 1] Games for November 15, 2025:")
    try:
        games = scraper.get_games_for_date("2025-11-15")
        print(f"  Found {len(games)} games")
        for game in games[:3]:
            print(f"    - {game.short_name} ({game.status})")
            if game.home_team.score is not None:
                print(f"      Score: {game.away_team.abbreviation} {game.away_team.score} @ {game.home_team.abbreviation} {game.home_team.score}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Test 2: Get boxscore for UConn vs BYU
    print("\n[TEST 2] Boxscore for UConn vs BYU (401812788):")
    try:
        boxscore = scraper.get_boxscore("401812788")
        print(f"  {boxscore.away_team.display_name} {boxscore.away_team.score} @ {boxscore.home_team.display_name} {boxscore.home_team.score}")
        print(f"  Status: {boxscore.status}")
        
        if boxscore.home_players:
            top_scorer = max(boxscore.home_players, key=lambda p: p.points)
            print(f"  Home top scorer: {top_scorer.name} - {top_scorer.points} pts")
        
        if boxscore.away_players:
            top_scorer = max(boxscore.away_players, key=lambda p: p.points)
            print(f"  Away top scorer: {top_scorer.name} - {top_scorer.points} pts")
            
    except Exception as e:
        print(f"  Error: {e}")
    
    # Test 3: Get play-by-play
    print("\n[TEST 3] Play-by-play sample:")
    try:
        pbp = scraper.get_play_by_play("401812788")
        print(f"  Total plays: {pbp.total_plays}")
        scoring_plays = pbp.get_scoring_plays()
        print(f"  Scoring plays: {len(scoring_plays)}")
        
        if scoring_plays:
            last_score = scoring_plays[-1]
            print(f"  Last score: {last_score.description}")
            print(f"    Score: {pbp.away_team.abbreviation} {last_score.score_away} - {pbp.home_team.abbreviation} {last_score.score_home}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\n" + "=" * 60)
    print("Tests complete!")