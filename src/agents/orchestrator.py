"""
Orchestrator Agent - Routes questions through the confidence cascade.

Architecture:
  Layer 1: Visual Context (highest confidence, <2s)
  Layer 2: Verified Reports (high confidence, <3s)
  Layer 3: SQL Generation (medium confidence, 5-15s)

The orchestrator tries each layer in order, returning when it gets
a high-confidence answer or exhausts all options.
"""

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from src.agents.visual_context import VisualContextAgent, VisualAgentResult
from src.models.responses import AgentResponse, ResponseSource, ConfidenceLevel
from src.services.anthropic import AnthropicService


class OrchestratorConfig(BaseModel):
    """Configuration for the orchestrator."""

    visual_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    enable_visual_layer: bool = True
    enable_sql_layer: bool = True
    db_path: Path = Field(default_factory=lambda: Path("data/ncaa_basketball.db"))
    screenshots_dir: Path = Field(default_factory=lambda: Path("data/screenshots"))

    model_config = {"extra": "forbid"}


class SQLGenerationResult(BaseModel):
    """Result from SQL generation layer."""

    query: str
    result: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    row_count: int = 0

    model_config = {"extra": "forbid"}


class Orchestrator:
    """
    Main orchestrator for the confidence cascade.

    Routes questions through layers based on confidence thresholds.
    """

    def __init__(
        self,
        api_key: str,
        config: Optional[OrchestratorConfig] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            api_key: Anthropic API key
            config: Optional configuration
        """
        self.config = config or OrchestratorConfig()
        self.anthropic = AnthropicService(api_key=api_key)

        # Initialize visual context agent
        self.visual_agent = VisualContextAgent(
            anthropic_service=self.anthropic,
            db_path=self.config.db_path,
            screenshots_dir=self.config.screenshots_dir,
        )

    def ask(
        self,
        question: str,
        game_id: Optional[str] = None,
    ) -> AgentResponse:
        """
        Route a question through the confidence cascade.

        Args:
            question: User's question
            game_id: Optional specific game to ask about

        Returns:
            AgentResponse with answer and metadata
        """
        start_time = time.time()

        # Layer 1: Visual Context
        if self.config.enable_visual_layer:
            visual_result = self._try_visual_layer(question, game_id)
            if visual_result and visual_result.confidence >= self.config.visual_confidence_threshold:
                return AgentResponse(
                    answer=visual_result.answer,
                    source=ResponseSource.VISUAL,
                    confidence=visual_result.confidence,
                    confidence_level=visual_result.confidence_level,
                    evidence=f"From screenshot: {visual_result.screenshot_path}",
                    dashboard_reference=visual_result.game_id,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    timestamp=datetime.now(timezone.utc),
                )

        # Layer 2: Verified Reports (stub for now - would use semantic layer)
        # This would match questions to pre-defined queries

        # Layer 3: SQL Generation
        if self.config.enable_sql_layer:
            sql_result = self._try_sql_layer(question, game_id)
            if sql_result and sql_result.confidence >= 0.5:
                return AgentResponse(
                    answer=sql_result.result,
                    source=ResponseSource.GENERATED,
                    confidence=sql_result.confidence,
                    confidence_level=self._get_confidence_level(sql_result.confidence),
                    sql_query=sql_result.query,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    timestamp=datetime.now(timezone.utc),
                )

        # No confident answer found
        return AgentResponse(
            answer="I couldn't find a confident answer to your question. Please try rephrasing or ask about a specific game.",
            source=ResponseSource.ERROR,
            confidence=0.0,
            confidence_level=ConfidenceLevel.NONE,
            processing_time_ms=int((time.time() - start_time) * 1000),
            timestamp=datetime.now(timezone.utc),
        )

    def _try_visual_layer(
        self,
        question: str,
        game_id: Optional[str],
    ) -> Optional[VisualAgentResult]:
        """Try to answer using visual context."""
        try:
            result = self.visual_agent.ask(question, game_id=game_id)
            if result.answer is not None:
                return result
        except Exception:
            pass
        return None

    def _try_sql_layer(
        self,
        question: str,
        game_id: Optional[str],
    ) -> Optional[SQLGenerationResult]:
        """Try to answer using SQL generation."""
        try:
            # Generate SQL using Claude
            sql_prompt = self._build_sql_prompt(question, game_id)
            response = self.anthropic.ask(
                question=sql_prompt,
                system_prompt=SQL_AGENT_SYSTEM_PROMPT,
            )

            # Extract SQL from response
            sql_query = self._extract_sql(response.content)
            if not sql_query:
                return None

            # Execute SQL
            result = self._execute_sql(sql_query)
            if result:
                return SQLGenerationResult(
                    query=sql_query,
                    result=result["answer"],
                    confidence=0.7,  # Medium confidence for generated SQL
                    row_count=result["row_count"],
                )
        except Exception:
            pass
        return None

    def _build_sql_prompt(self, question: str, game_id: Optional[str]) -> str:
        """Build prompt for SQL generation."""
        schema_info = self._get_schema_info()

        prompt = f"""Given this database schema:
{schema_info}

User question: {question}
"""
        if game_id:
            prompt += f"\nContext: The user is asking about game_id = '{game_id}'"

        prompt += "\n\nGenerate a SQL query to answer this question."
        return prompt

    def _get_schema_info(self) -> str:
        """Get database schema information."""
        return """
Tables:
1. games (game_id, game_date, away_team_name, home_team_name, away_team_abbrev, home_team_abbrev, away_team_score, home_team_score, venue)
2. players (id, game_id, team_name, team_abbrev, player_name, position, starter, minutes, points, rebounds, assists, steals, blocks, turnovers, fouls, fg_made, fg_attempted, fg3_made, fg3_attempted, ft_made, ft_attempted, plus_minus)
3. screenshots (id, game_id, file_path, file_name, captured_at, width, height, file_size_bytes)
"""

    def _extract_sql(self, content: str) -> Optional[str]:
        """Extract SQL query from Claude's response."""
        # Look for SQL between code blocks
        if "```sql" in content:
            start = content.find("```sql") + 6
            end = content.find("```", start)
            if end > start:
                return content[start:end].strip()

        # Look for SELECT statements
        lines = content.split("\n")
        sql_lines = []
        in_sql = False
        for line in lines:
            if line.strip().upper().startswith("SELECT"):
                in_sql = True
            if in_sql:
                sql_lines.append(line)
                if ";" in line:
                    break

        if sql_lines:
            return "\n".join(sql_lines).strip()

        return None

    def _execute_sql(self, query: str) -> Optional[dict]:
        """Execute SQL query safely."""
        # Only allow SELECT queries
        if not query.strip().upper().startswith("SELECT"):
            return None

        try:
            conn = sqlite3.connect(self.config.db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            conn.close()

            if not rows:
                return {"answer": "No results found.", "row_count": 0}

            # Format result
            if len(rows) == 1 and len(columns) == 1:
                answer = str(rows[0][0])
            else:
                # Format as table
                result_lines = []
                for row in rows[:10]:  # Limit to 10 rows
                    row_str = ", ".join(f"{col}: {val}" for col, val in zip(columns, row))
                    result_lines.append(row_str)
                answer = "\n".join(result_lines)
                if len(rows) > 10:
                    answer += f"\n... and {len(rows) - 10} more rows"

            return {"answer": answer, "row_count": len(rows)}
        except Exception:
            return None

    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Convert confidence score to level."""
        if confidence >= 0.85:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.3:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.NONE

    def list_available_games(self) -> list[dict]:
        """List all games available for querying."""
        return self.visual_agent.list_available_games()


SQL_AGENT_SYSTEM_PROMPT = """You are a SQL expert for NCAA basketball data.

Your role:
1. Generate correct SQLite queries to answer user questions
2. Only use tables and columns from the provided schema
3. Always use proper JOIN conditions
4. Limit results to reasonable numbers

Rules:
- ONLY generate SELECT queries (no INSERT, UPDATE, DELETE)
- Always include ORDER BY for consistent results
- Use LIMIT when appropriate
- Return the SQL in a ```sql code block

Example:
User: Who scored the most points?
```sql
SELECT player_name, points, team_name
FROM players
ORDER BY points DESC
LIMIT 1;
```
"""


def create_orchestrator(
    api_key: str,
    db_path: Optional[Path] = None,
    screenshots_dir: Optional[Path] = None,
) -> Orchestrator:
    """
    Factory function to create an orchestrator.

    Args:
        api_key: Anthropic API key
        db_path: Path to SQLite database
        screenshots_dir: Path to screenshots directory

    Returns:
        Configured Orchestrator
    """
    config = OrchestratorConfig()
    if db_path:
        config.db_path = db_path
    if screenshots_dir:
        config.screenshots_dir = screenshots_dir

    return Orchestrator(api_key=api_key, config=config)
