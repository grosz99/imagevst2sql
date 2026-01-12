"""
Visual Context Agent - answers questions using dashboard screenshots.

This is Layer 1 of the confidence cascade:
- Input: Dashboard screenshots + user question
- Confidence: HIGHEST (human-validated visuals)
- Latency: <2s (no DB hit)
- Best for: "What should I focus on?" / "What's trending?"
"""

import sqlite3
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from src.services.anthropic import AnthropicService, VisionResponse


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class VisualAgentResult(BaseModel):
    """
    Result from the Visual Context Agent.

    CRITICAL: Never return fake answers.
    If confidence < 0.5, answer MUST be None.
    """

    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    answer: Optional[str] = None
    game_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    captured_at: Optional[datetime] = None
    missing_info: Optional[str] = None
    tokens_used: int = 0
    processing_time_ms: int = 0

    @model_validator(mode="after")
    def validate_answer_confidence(self) -> "VisualAgentResult":
        """Ensure answer is None when confidence is too low."""
        if self.confidence < 0.5 and self.answer is not None:
            raise ValueError(
                f"Answer must be None when confidence ({self.confidence}) < 0.5"
            )
        return self

    model_config = {"extra": "forbid"}


# System prompt for the Visual Context Agent
VISUAL_AGENT_SYSTEM_PROMPT = """You are a Visual Context Agent analyzing NCAA basketball boxscore dashboards.

Your role:
1. Extract specific data from the screenshot when asked
2. Provide accurate numerical answers based on what you see
3. Report confidence in your answer (0.0 to 1.0)

Rules:
- ONLY answer based on what is VISIBLE in the screenshot
- If the information is not visible, say so clearly
- Always include the exact numbers you see
- Format your response as:
  ANSWER: [your answer with specific numbers]
  CONFIDENCE: [0.0-1.0]
  REASONING: [brief explanation of what you saw]

If you cannot find the information:
  ANSWER: NOT_FOUND
  CONFIDENCE: 0.0
  MISSING: [what information would be needed]
"""


class VisualContextAgent:
    """
    Agent that answers questions using dashboard screenshots.

    Uses Claude Vision API to parse visual content and extract answers.
    """

    def __init__(
        self,
        anthropic_service: AnthropicService,
        db_path: Path,
        screenshots_dir: Path,
    ):
        """
        Initialize Visual Context Agent.

        Args:
            anthropic_service: Anthropic API service
            db_path: Path to SQLite database
            screenshots_dir: Directory containing screenshots
        """
        self.anthropic = anthropic_service
        self.db_path = db_path
        self.screenshots_dir = screenshots_dir

    def _resolve_path(self, db_path: str) -> Path:
        """Resolve a database path to an absolute path."""
        # Get project root (parent of src directory)
        project_root = Path(__file__).parent.parent.parent
        resolved = project_root / db_path
        if resolved.exists():
            return resolved
        # Fallback: try as absolute path
        return Path(db_path)

    def get_latest_screenshot(self, game_id: Optional[str] = None) -> Optional[Path]:
        """Get the most recent screenshot, optionally for a specific game."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if game_id:
            cursor.execute(
                "SELECT file_path FROM screenshots WHERE game_id = ? ORDER BY captured_at DESC LIMIT 1",
                (game_id,),
            )
        else:
            cursor.execute(
                "SELECT file_path FROM screenshots ORDER BY captured_at DESC LIMIT 1"
            )

        row = cursor.fetchone()
        conn.close()

        if row:
            return self._resolve_path(row[0])
        return None

    def find_screenshot_by_team(self, question: str) -> Optional[tuple[str, Path]]:
        """Find a screenshot by looking for team names in the question."""
        # Team aliases to search for
        team_keywords = {
            "duke": ["duke", "blue devils"],
            "wake": ["wake", "wake forest", "demon deacons"],
            "unc": ["unc", "tar heels", "north carolina"],
            "texas": ["texas", "longhorns"],
            "byu": ["byu", "cougars"],
            "utah": ["utah", "utes"],
            "smu": ["smu", "mustangs"],
            "auburn": ["auburn", "tigers"],
            "arkansas": ["arkansas", "razorbacks"],
            "purdue": ["purdue", "boilermakers"],
            "alabama": ["alabama", "crimson tide", "bama"],
            "gonzaga": ["gonzaga", "bulldogs", "zags"],
            "uva": ["uva", "virginia cavaliers", "cavaliers"],
            "stanford": ["stanford", "cardinal"],
            "arizona": ["arizona", "wildcats", "ariz"],
            "tcu": ["tcu", "horned frogs"],
            "colorado": ["colorado", "buffaloes", "buffs", "colo"],
            "texas tech": ["texas tech", "red raiders", "ttu"],
            "iowa state": ["iowa state", "cyclones", "isu"],
            "oklahoma state": ["oklahoma state", "cowboys", "okst"],
            "south carolina": ["south carolina", "gamecocks", "sc"],
            "georgia": ["georgia", "bulldogs", "uga"],
        }

        question_lower = question.lower()

        # First, find all teams mentioned in the question
        teams_found = []
        for team_key, aliases in team_keywords.items():
            for alias in aliases:
                if alias in question_lower:
                    teams_found.append(team_key)
                    break  # Found this team, move to next

        # Try each team found until we get a screenshot
        for team_key in teams_found:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT g.game_id, s.file_path
                FROM games g
                JOIN screenshots s ON g.game_id = s.game_id
                WHERE LOWER(g.home_team_name) LIKE ?
                   OR LOWER(g.away_team_name) LIKE ?
                   OR LOWER(g.home_team_abbrev) LIKE ?
                   OR LOWER(g.away_team_abbrev) LIKE ?
                LIMIT 1
            """, (f"%{team_key}%", f"%{team_key}%", f"%{team_key}%", f"%{team_key}%"))
            row = cursor.fetchone()
            conn.close()

            if row:
                resolved_path = self._resolve_path(row[1])
                if resolved_path.exists():
                    return (row[0], resolved_path)

        return None

    def get_screenshot_for_game(self, game_id: str) -> Optional[Path]:
        """Get screenshot path for a specific game."""
        # First check database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_path FROM screenshots WHERE game_id = ? LIMIT 1", (game_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            resolved_path = self._resolve_path(row[0])
            if resolved_path.exists():
                return resolved_path

        # Fallback: search screenshots directory by game_id pattern
        for f in self.screenshots_dir.glob("*.png"):
            if game_id in f.stem:
                return f

        return None

    def list_available_games(self) -> list[dict]:
        """List all games with screenshots available."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT g.game_id, g.away_team_name, g.home_team_name,
                   g.away_team_score, g.home_team_score, g.game_date
            FROM games g
            INNER JOIN screenshots s ON g.game_id = s.game_id
            ORDER BY g.game_date DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "game_id": r[0],
                "away_team": r[1],
                "home_team": r[2],
                "away_score": r[3],
                "home_score": r[4],
                "game_date": r[5],
            }
            for r in rows
        ]

    def ask(
        self,
        question: str,
        game_id: Optional[str] = None,
        screenshot_path: Optional[Path] = None,
    ) -> VisualAgentResult:
        """
        Ask a question about a game using its screenshot.

        Args:
            question: The question to ask
            game_id: Optional specific game ID
            screenshot_path: Optional direct path to screenshot

        Returns:
            VisualAgentResult with answer and confidence
        """
        import time

        start_time = time.time()

        # Get screenshot
        if screenshot_path is None:
            if game_id:
                screenshot_path = self.get_screenshot_for_game(game_id)
            else:
                # Try to find a screenshot matching a team mentioned in the question
                team_match = self.find_screenshot_by_team(question)
                if team_match:
                    game_id, screenshot_path = team_match
                else:
                    screenshot_path = self.get_latest_screenshot()

        if screenshot_path is None or not screenshot_path.exists():
            return VisualAgentResult(
                confidence=0.0,
                confidence_level=ConfidenceLevel.NONE,
                answer=None,
                game_id=game_id,
                missing_info="No screenshot available for this game",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        # Call Claude Vision
        try:
            response = self.anthropic.ask_about_image(
                image_path=screenshot_path,
                question=question,
                system_prompt=VISUAL_AGENT_SYSTEM_PROMPT,
            )
        except Exception as e:
            return VisualAgentResult(
                confidence=0.0,
                confidence_level=ConfidenceLevel.NONE,
                answer=None,
                game_id=game_id,
                screenshot_path=str(screenshot_path),
                missing_info=f"API error: {str(e)}",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        # Parse response
        result = self._parse_response(response, game_id, screenshot_path)
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        result.tokens_used = response.input_tokens + response.output_tokens

        return result

    def _parse_response(
        self, response: VisionResponse, game_id: Optional[str], screenshot_path: Path
    ) -> VisualAgentResult:
        """Parse the Claude response into a structured result."""
        content = response.content

        # Extract answer
        answer = None
        confidence = 0.0
        missing_info = None

        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("ANSWER:"):
                answer_text = line.replace("ANSWER:", "").strip()
                if answer_text != "NOT_FOUND":
                    answer = answer_text
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.replace("CONFIDENCE:", "").strip())
                    confidence = max(0.0, min(1.0, confidence))
                except ValueError:
                    confidence = 0.5
            elif line.startswith("MISSING:"):
                missing_info = line.replace("MISSING:", "").strip()

        # Determine confidence level
        if confidence >= 0.85:
            level = ConfidenceLevel.HIGH
        elif confidence >= 0.6:
            level = ConfidenceLevel.MEDIUM
        elif confidence >= 0.3:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.NONE

        # If confidence too low, don't return answer
        if confidence < 0.5:
            answer = None

        return VisualAgentResult(
            confidence=confidence,
            confidence_level=level,
            answer=answer,
            game_id=game_id,
            screenshot_path=str(screenshot_path),
            missing_info=missing_info,
        )


def create_visual_agent(
    api_key: str,
    db_path: Optional[Path] = None,
    screenshots_dir: Optional[Path] = None,
) -> VisualContextAgent:
    """
    Factory function to create a Visual Context Agent.

    Args:
        api_key: Anthropic API key
        db_path: Path to SQLite database (default: data/ncaa_basketball.db)
        screenshots_dir: Path to screenshots (default: data/screenshots)

    Returns:
        Configured VisualContextAgent
    """
    if db_path is None:
        db_path = Path(__file__).parent.parent.parent / "data" / "ncaa_basketball.db"
    if screenshots_dir is None:
        screenshots_dir = Path(__file__).parent.parent.parent / "data" / "screenshots"

    anthropic_service = AnthropicService(api_key=api_key)

    return VisualContextAgent(
        anthropic_service=anthropic_service,
        db_path=db_path,
        screenshots_dir=screenshots_dir,
    )
