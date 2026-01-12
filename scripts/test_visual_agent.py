"""
Test the Visual Context Agent with captured screenshots.

Loads API key from .env file (never committed to git).
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from src.agents.visual_context import create_visual_agent


def main():
    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not found")
        print()
        print("Setup:")
        print("  1. Copy .env.example to .env")
        print("  2. Add your Anthropic API key to .env")
        print("  3. Run this script again")
        return

    print("=" * 60)
    print("Visual Context Agent Test")
    print("=" * 60)

    # Create agent
    agent = create_visual_agent(api_key=api_key)

    # Check for screenshots
    screenshots_dir = Path(__file__).parent.parent / "data" / "screenshots"
    screenshots = list(screenshots_dir.glob("*.png"))

    if not screenshots:
        print("ERROR: No screenshots found. Run capture_screenshots.py first.")
        return

    print(f"Found {len(screenshots)} screenshots")
    print(f"Using: {screenshots[0].name}")

    # Test questions
    test_questions = [
        "Who was the top scorer in this game and how many points did they score?",
        "What was the final score of this game?",
        "Which team had more rebounds?",
        "How many 3-pointers did the away team make?",
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n[Question {i}] {question}")
        print("-" * 50)

        result = agent.ask(question, screenshot_path=screenshots[0])

        print(f"Answer: {result.answer}")
        print(f"Confidence: {result.confidence:.2f} ({result.confidence_level})")
        if result.missing_info:
            print(f"Missing: {result.missing_info}")
        print(f"Tokens: {result.tokens_used}, Time: {result.processing_time_ms}ms")

    print("\n" + "=" * 60)
    print("Test complete!")


if __name__ == "__main__":
    main()
