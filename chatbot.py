"""
NCAA Basketball Analytics Chatbot - Competition Mode

All 3 agents race to answer your question in parallel:
1. Visual Context (screenshots)
2. Semantic Layer (pre-defined queries)
3. SQL Generation (LLM-generated queries)

See which one is fastest and most accurate!

Run with: streamlit run chatbot.py --server.port 8504
"""

import os
import sqlite3
import time
import concurrent.futures
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from src.services.anthropic import AnthropicService
from src.agents.visual_context import VisualContextAgent
from src.agents.semantic_layer import SemanticLayer
from src.models.responses import ResponseSource, ConfidenceLevel


DB_PATH = Path(__file__).parent / "data" / "ncaa_basketball.db"
SCREENSHOTS_DIR = Path(__file__).parent / "data" / "screenshots"


@dataclass
class AgentResult:
    """Result from an agent."""
    agent_name: str
    answer: Optional[str]
    confidence: float
    time_ms: int
    sql_query: Optional[str] = None
    error: Optional[str] = None
    source_info: Optional[str] = None


def get_api_key() -> str:
    """Get API key from environment or session state."""
    if "api_key" in st.session_state and st.session_state.api_key:
        return st.session_state.api_key
    return os.environ.get("ANTHROPIC_API_KEY", "")


def get_games_for_selector() -> list[tuple[str, str]]:
    """Get games for the dropdown selector."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT g.game_id, g.away_team_abbrev, g.home_team_abbrev,
               g.away_team_score, g.home_team_score, g.game_date,
               (SELECT COUNT(*) FROM screenshots s WHERE s.game_id = g.game_id) as has_screenshot
        FROM games g
        ORDER BY g.game_date DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        game_id, away, home, away_score, home_score, date, has_ss = row
        icon = "📸" if has_ss > 0 else "📊"
        label = f"{icon} {away} {away_score} @ {home} {home_score} ({date[:10]})"
        results.append((game_id, label))

    return results


def run_visual_agent(question: str, api_key: str, game_id: Optional[str]) -> AgentResult:
    """Run the visual context agent."""
    start = time.time()
    try:
        anthropic = AnthropicService(api_key=api_key)
        agent = VisualContextAgent(
            anthropic_service=anthropic,
            db_path=DB_PATH,
            screenshots_dir=SCREENSHOTS_DIR,
        )
        result = agent.ask(question, game_id=game_id)
        elapsed = int((time.time() - start) * 1000)

        return AgentResult(
            agent_name="Visual Context",
            answer=result.answer,
            confidence=result.confidence,
            time_ms=elapsed,
            source_info=result.screenshot_path,
        )
    except Exception as e:
        return AgentResult(
            agent_name="Visual Context",
            answer=None,
            confidence=0.0,
            time_ms=int((time.time() - start) * 1000),
            error=str(e),
        )


def run_semantic_agent(question: str) -> AgentResult:
    """Run the semantic layer agent."""
    start = time.time()
    try:
        layer = SemanticLayer(db_path=DB_PATH)
        result = layer.ask(question)
        elapsed = int((time.time() - start) * 1000)

        if result:
            return AgentResult(
                agent_name="Semantic Layer",
                answer=result.answer,
                confidence=result.confidence,
                time_ms=elapsed,
                sql_query=result.sql_executed,
                source_info=f"Matched: {result.query_name}",
            )
        else:
            return AgentResult(
                agent_name="Semantic Layer",
                answer=None,
                confidence=0.0,
                time_ms=elapsed,
                error="No pattern matched",
            )
    except Exception as e:
        return AgentResult(
            agent_name="Semantic Layer",
            answer=None,
            confidence=0.0,
            time_ms=int((time.time() - start) * 1000),
            error=str(e),
        )


def run_sql_agent(question: str, api_key: str, game_id: Optional[str]) -> AgentResult:
    """Run the SQL generation agent."""
    start = time.time()
    try:
        anthropic = AnthropicService(api_key=api_key)

        schema_info = """
Tables:
1. games (game_id, game_date, away_team_name, home_team_name, away_team_abbrev, home_team_abbrev, away_team_score, home_team_score, venue)
2. players (id, game_id, team_name, team_abbrev, player_name, position, starter, minutes, points, rebounds, assists, steals, blocks, turnovers, fouls, fg_made, fg_attempted, fg3_made, fg3_attempted, ft_made, ft_attempted, plus_minus, jersey)
"""

        prompt = f"""Given this SQLite database schema:
{schema_info}

User question: {question}
"""
        if game_id:
            prompt += f"\nContext: Focus on game_id = '{game_id}'"

        prompt += """

Generate a SQL query to answer this question. Return ONLY the SQL in a ```sql code block.
Rules:
- Only SELECT queries
- Use appropriate JOINs
- LIMIT results to 10 unless counting
- ORDER BY for consistent results"""

        response = anthropic.ask(question=prompt)

        # Extract SQL
        sql_query = None
        content = response.content
        if "```sql" in content:
            sql_start = content.find("```sql") + 6
            sql_end = content.find("```", sql_start)
            if sql_end > sql_start:
                sql_query = content[sql_start:sql_end].strip()

        if not sql_query or not sql_query.upper().startswith("SELECT"):
            return AgentResult(
                agent_name="SQL Generation",
                answer=None,
                confidence=0.0,
                time_ms=int((time.time() - start) * 1000),
                error="Failed to generate valid SQL",
            )

        # Execute SQL
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()

        elapsed = int((time.time() - start) * 1000)

        if not rows:
            return AgentResult(
                agent_name="SQL Generation",
                answer="No results found.",
                confidence=0.5,
                time_ms=elapsed,
                sql_query=sql_query,
            )

        # Format result
        if len(rows) == 1 and len(columns) == 1:
            answer = str(rows[0][0])
        else:
            result_lines = []
            for row in rows[:5]:
                row_str = ", ".join(f"{col}: {val}" for col, val in zip(columns, row))
                result_lines.append(row_str)
            answer = "\n".join(result_lines)
            if len(rows) > 5:
                answer += f"\n... and {len(rows) - 5} more"

        return AgentResult(
            agent_name="SQL Generation",
            answer=answer,
            confidence=0.7,
            time_ms=elapsed,
            sql_query=sql_query,
        )
    except Exception as e:
        return AgentResult(
            agent_name="SQL Generation",
            answer=None,
            confidence=0.0,
            time_ms=int((time.time() - start) * 1000),
            error=str(e),
        )


def render_agent_result(result: AgentResult):
    """Render a single agent's result as a card."""
    # Determine status color
    if result.error:
        status_color = "🔴"
        status = "Error"
    elif result.answer:
        status_color = "🟢"
        status = "Success"
    else:
        status_color = "🟡"
        status = "No Answer"

    # Agent icons
    icons = {
        "Visual Context": "📷",
        "Semantic Layer": "📊",
        "SQL Generation": "🔍",
    }
    icon = icons.get(result.agent_name, "")

    st.markdown(f"### {icon} {result.agent_name}")
    st.markdown(f"**Status:** {status_color} {status} | **Time:** {result.time_ms}ms | **Confidence:** {result.confidence*100:.0f}%")

    if result.answer:
        st.success(result.answer)
    elif result.error:
        st.error(result.error)
    else:
        st.warning("No answer found")

    if result.sql_query:
        with st.expander("SQL Query"):
            st.code(result.sql_query, language="sql")

    # Show screenshot for Visual Context agent
    if result.agent_name == "Visual Context" and result.source_info:
        screenshot_path = Path(result.source_info)
        if screenshot_path.exists():
            with st.expander("Screenshot Used", expanded=True):
                st.image(str(screenshot_path), use_container_width=True)
        else:
            st.caption(f"Source: {result.source_info}")
    elif result.source_info:
        st.caption(f"Source: {result.source_info}")


def main():
    st.set_page_config(
        page_title="NCAA Basketball - Agent Competition",
        page_icon="🏀",
        layout="wide"
    )

    st.title("🏀 NCAA Basketball - Agent Competition")
    st.caption("All 3 agents race to answer your question. See who's fastest and most accurate!")

    # Sidebar
    with st.sidebar:
        st.header("Settings")

        env_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not env_key:
            api_key = st.text_input("Anthropic API Key", type="password")
            if api_key:
                st.session_state.api_key = api_key
        else:
            st.success("API Key loaded")

        st.divider()

        st.subheader("Game Filter (optional)")
        games = get_games_for_selector()

        if games:
            selected_idx = st.selectbox(
                "Focus on a game",
                range(len(games) + 1),
                format_func=lambda i: "All Games" if i == 0 else games[i-1][1]
            )
            selected_game_id = None if selected_idx == 0 else games[selected_idx-1][0]
        else:
            selected_game_id = None

        st.divider()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        games_count = cursor.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        screenshots_count = len(list(SCREENSHOTS_DIR.glob("*.png"))) if SCREENSHOTS_DIR.exists() else 0
        conn.close()

        col1, col2 = st.columns(2)
        col1.metric("Games", games_count)
        col2.metric("Screenshots", screenshots_count)

        st.divider()
        if st.button("Clear History"):
            st.session_state.messages = []
            st.rerun()

    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask about NCAA basketball..."):
        api_key = get_api_key()
        if not api_key:
            st.error("Please enter API key")
            return

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            st.markdown("### 🏁 Race Results")

            # Create placeholders for real-time updates
            col1, col2, col3 = st.columns(3)

            with col1:
                visual_placeholder = st.empty()
                visual_placeholder.info("📷 **Visual Agent**\n\n⏳ Running...")

            with col2:
                semantic_placeholder = st.empty()
                semantic_placeholder.info("📊 **Semantic Agent**\n\n⏳ Running...")

            with col3:
                sql_placeholder = st.empty()
                sql_placeholder.info("🔍 **SQL Agent**\n\n⏳ Running...")

            # Run all agents in parallel using ThreadPoolExecutor
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # Submit all tasks
                visual_future = executor.submit(run_visual_agent, prompt, api_key, selected_game_id)
                semantic_future = executor.submit(run_semantic_agent, prompt)
                sql_future = executor.submit(run_sql_agent, prompt, api_key, selected_game_id)

                # Process as they complete
                future_to_placeholder = {
                    visual_future: (visual_placeholder, "Visual"),
                    semantic_future: (semantic_placeholder, "Semantic"),
                    sql_future: (sql_placeholder, "SQL"),
                }

                for future in concurrent.futures.as_completed(future_to_placeholder):
                    placeholder, name = future_to_placeholder[future]
                    try:
                        result = future.result()
                        results.append(result)

                        # Update placeholder immediately
                        with placeholder.container():
                            if result.answer:
                                st.success(f"**{result.agent_name}**\n\n✅ {result.time_ms}ms\n\n{result.answer[:100]}...")
                            elif result.error:
                                st.error(f"**{result.agent_name}**\n\n❌ {result.error[:50]}")
                            else:
                                st.warning(f"**{result.agent_name}**\n\n⚠️ No match")
                    except Exception as e:
                        with placeholder.container():
                            st.error(f"**{name} Agent**\n\n❌ {str(e)[:50]}")

            # Clear placeholders and show final results
            visual_placeholder.empty()
            semantic_placeholder.empty()
            sql_placeholder.empty()

            st.divider()
            st.markdown("### 📊 Results Comparison")

            # Show all results side by side (no ranking)
            cols = st.columns(3)
            for i, result in enumerate(results):
                with cols[i]:
                    render_agent_result(result)

            # Summary
            successful = [r for r in results if r.answer]
            if successful:
                st.divider()
                st.markdown("### Summary")
                for r in successful:
                    st.markdown(f"- **{r.agent_name}** ({r.time_ms}ms, {r.confidence*100:.0f}%): {r.answer[:150]}")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "\n".join([f"**{r.agent_name}** ({r.time_ms}ms): {r.answer}" for r in successful])
                })
            else:
                st.warning("No agent could answer this question.")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "No agent could answer this question."
                })

    # Example questions
    if not st.session_state.messages:
        st.markdown("### Try these questions:")
        examples = [
            "Who scored the most points for Duke?",
            "Who had the most assists?",
            "What was the score of the Wake Forest game?",
            "Who made the most three pointers for wake?",
            "Which team won by the biggest margin?",
        ]
        for ex in examples:
            st.markdown(f"- {ex}")


if __name__ == "__main__":
    main()
