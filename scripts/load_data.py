"""
Load NCAA basketball data for 2025-2026 season.
Run this to populate the SQLite database.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.cbbpy_data import CBBDataService


def main():
    service = CBBDataService()

    print(f"Database: {service.db_path}")
    print(f"Current game count: {service.get_game_count()}")

    # Load a single day to start (Dec 7, 2025 - should have many games)
    test_date = "2025-12-07"
    print(f"\nFetching games for {test_date}...")

    game_ids = service.fetch_games_for_date(test_date)
    print(f"Found {len(game_ids)} games")

    # Load first 5 games to keep it quick
    loaded = 0
    for game_id in game_ids[:5]:
        print(f"  Loading game {game_id}...")
        try:
            if service.fetch_and_store_game(game_id):
                loaded += 1
        except Exception as e:
            print(f"    Error: {e}")

    print(f"\nLoaded {loaded} games")
    print(f"Total games in DB: {service.get_game_count()}")

    # Show sample data
    print("\n--- Recent Games ---")
    print(service.get_recent_games(5).to_string(index=False))

    print("\n--- Top Scorers ---")
    print(service.get_top_scorers(5).to_string(index=False))


if __name__ == "__main__":
    main()
