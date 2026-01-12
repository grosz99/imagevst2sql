"""
Semantic Layer - Pre-defined verified queries for common questions.

This is Layer 2 of the confidence cascade:
- Input: Question → Pattern match → Pre-approved SQL
- Confidence: HIGH (deterministic, pre-approved queries)
- Latency: <1s (no LLM call needed)
- Best for: Standard reports, common metrics
"""

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SemanticQuery:
    """A pre-defined semantic query."""
    name: str
    description: str
    patterns: list[str]  # Regex patterns to match
    sql: str
    format_template: str  # How to format the result


# Pre-defined queries for common questions
SEMANTIC_QUERIES = [
    SemanticQuery(
        name="leading_scorer_game",
        description="Find the leading scorer in a specific game",
        patterns=[
            r"(?:who|which player).*(?:leading|top|most).*scor(?:er|ed|ing).*(?:duke|wake|unc|carolina|texas|byu|utah)",
            r"(?:leading|top|highest).*scor(?:er|ed|ing).*(?:in|for).*(?:the|this)?\s*(?:duke|wake|unc|carolina|texas|byu|utah)",
        ],
        sql="""
            SELECT p.player_name, p.points, p.team_name, g.away_team_name, g.home_team_name
            FROM players p
            JOIN games g ON p.game_id = g.game_id
            WHERE (LOWER(g.home_team_name) LIKE '%{team}%' OR LOWER(g.away_team_name) LIKE '%{team}%')
            ORDER BY p.points DESC
            LIMIT 1
        """,
        format_template="{player_name} with {points} points ({team_name})"
    ),
    SemanticQuery(
        name="leading_scorer_overall",
        description="Find the leading scorer across all games",
        patterns=[
            r"(?:who|which player).*(?:most|highest|top).*points?(?:\s+overall)?",
            r"(?:leading|top).*scor(?:er|ed|ing).*(?:overall|across|all)",
            r"(?:most|highest).*points?.*(?:overall|all games|any game)",
        ],
        sql="""
            SELECT player_name, points, team_name, game_id
            FROM players
            ORDER BY points DESC
            LIMIT 1
        """,
        format_template="{player_name} scored {points} points ({team_name})"
    ),
    SemanticQuery(
        name="most_assists",
        description="Find player with most assists",
        patterns=[
            r"(?:who|which player).*(?:most|highest|top).*assists?",
            r"(?:most|highest).*assists?",
            r"assist.*leader",
        ],
        sql="""
            SELECT player_name, assists, team_name
            FROM players
            ORDER BY assists DESC
            LIMIT 1
        """,
        format_template="{player_name} with {assists} assists ({team_name})"
    ),
    SemanticQuery(
        name="most_rebounds",
        description="Find player with most rebounds",
        patterns=[
            r"(?:who|which player).*(?:most|highest|top).*rebounds?",
            r"(?:most|highest).*rebounds?",
            r"rebound.*leader",
        ],
        sql="""
            SELECT player_name, rebounds, team_name
            FROM players
            ORDER BY rebounds DESC
            LIMIT 1
        """,
        format_template="{player_name} with {rebounds} rebounds ({team_name})"
    ),
    SemanticQuery(
        name="most_3pointers",
        description="Find player with most 3-pointers",
        patterns=[
            r"(?:who|which player).*(?:most|highest|top).*(?:3|three).*(?:pointer|pt)",
            r"(?:most|highest).*(?:3|three).*(?:pointer|pt|made)",
            r"(?:3|three).*point.*leader",
        ],
        sql="""
            SELECT player_name, fg3_made, team_name
            FROM players
            ORDER BY fg3_made DESC
            LIMIT 1
        """,
        format_template="{player_name} made {fg3_made} three-pointers ({team_name})"
    ),
    SemanticQuery(
        name="game_score",
        description="Get final score of a game",
        patterns=[
            r"(?:what|final).*score.*(?:duke|wake|unc|carolina|texas|byu|utah)",
            r"(?:duke|wake|unc|carolina|texas|byu|utah).*(?:score|beat|lost|won)",
        ],
        sql="""
            SELECT away_team_name, away_team_score, home_team_name, home_team_score
            FROM games
            WHERE LOWER(home_team_name) LIKE '%{team}%' OR LOWER(away_team_name) LIKE '%{team}%'
            LIMIT 1
        """,
        format_template="{away_team_name} {away_team_score} - {home_team_name} {home_team_score}"
    ),
    SemanticQuery(
        name="biggest_win",
        description="Find game with largest margin of victory",
        patterns=[
            r"(?:biggest|largest).*(?:win|margin|blowout)",
            r"(?:won|beat).*(?:by|with).*(?:most|biggest|largest)",
        ],
        sql="""
            SELECT away_team_name, away_team_score, home_team_name, home_team_score,
                   ABS(home_team_score - away_team_score) as margin
            FROM games
            ORDER BY margin DESC
            LIMIT 1
        """,
        format_template="{home_team_name} {home_team_score} vs {away_team_name} {away_team_score} (margin: {margin})"
    ),
    SemanticQuery(
        name="total_games",
        description="Count total games",
        patterns=[
            r"how many games",
            r"total.*games",
            r"number of games",
        ],
        sql="SELECT COUNT(*) as count FROM games",
        format_template="{count} games in database"
    ),
]

# Team name mapping for SQL queries
TEAM_ALIASES = {
    "duke": "duke",
    "blue devils": "duke",
    "wake": "wake forest",
    "wake forest": "wake forest",
    "demon deacons": "wake forest",
    "unc": "north carolina",
    "carolina": "north carolina",
    "tar heels": "north carolina",
    "texas": "texas",
    "longhorns": "texas",
    "byu": "byu",
    "cougars": "byu",
    "utah": "utah",
    "utes": "utah",
    "smu": "smu",
    "mustangs": "smu",
}


@dataclass
class SemanticResult:
    """Result from semantic layer."""
    answer: str
    query_name: str
    sql_executed: str
    confidence: float = 0.9  # High confidence for matched patterns


class SemanticLayer:
    """
    Matches questions to pre-defined verified queries.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.queries = SEMANTIC_QUERIES

    def match_query(self, question: str) -> Optional[tuple[SemanticQuery, dict]]:
        """
        Try to match question to a pre-defined query.

        Returns tuple of (matched_query, extracted_params) or None
        """
        question_lower = question.lower()

        for query in self.queries:
            for pattern in query.patterns:
                match = re.search(pattern, question_lower, re.IGNORECASE)
                if match:
                    # Extract parameters (like team name)
                    params = {}

                    # Check for team references
                    for alias, team in TEAM_ALIASES.items():
                        if alias in question_lower:
                            params["team"] = team
                            break

                    return (query, params)

        return None

    def ask(self, question: str) -> Optional[SemanticResult]:
        """
        Try to answer question using semantic layer.

        Returns SemanticResult if matched, None otherwise.
        """
        match_result = self.match_query(question)
        if not match_result:
            return None

        query, params = match_result

        # Format SQL with parameters
        sql = query.sql.format(**params) if params else query.sql

        # Execute query
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            # Format result
            row_dict = dict(row)
            answer = query.format_template.format(**row_dict)

            return SemanticResult(
                answer=answer,
                query_name=query.name,
                sql_executed=sql.strip(),
                confidence=0.9,
            )
        except Exception as e:
            return None


def create_semantic_layer(db_path: Optional[Path] = None) -> SemanticLayer:
    """Factory function to create semantic layer."""
    if db_path is None:
        db_path = Path(__file__).parent.parent.parent / "data" / "ncaa_basketball.db"
    return SemanticLayer(db_path=db_path)
