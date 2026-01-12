"""
Capture screenshots of each game boxscore from the Streamlit dashboard.
Stores images in data/screenshots/ folder and metadata in SQLite.
"""

import base64
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

DB_PATH = Path(__file__).parent.parent / "data" / "ncaa_basketball.db"
SCREENSHOTS_DIR = Path(__file__).parent.parent / "data" / "screenshots"
DASHBOARD_URL = "http://localhost:8503"


def init_screenshots_table():
    """Create screenshots table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            width INTEGER,
            height INTEGER,
            file_size_bytes INTEGER,
            FOREIGN KEY (game_id) REFERENCES games(game_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_screenshots_game ON screenshots(game_id)")
    conn.commit()
    conn.close()


def store_screenshot_metadata(game_id: str, file_path: Path, width: int, height: int):
    """Store screenshot metadata in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    file_size = file_path.stat().st_size if file_path.exists() else 0

    cursor.execute("""
        INSERT INTO screenshots (game_id, file_path, file_name, captured_at, width, height, file_size_bytes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        game_id,
        str(file_path),
        file_path.name,
        datetime.utcnow().isoformat(),
        width,
        height,
        file_size
    ))
    conn.commit()
    conn.close()


def get_game_ids() -> list[tuple[str, str]]:
    """Get all game IDs and labels from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT game_id, away_team_abbrev, home_team_abbrev,
               away_team_score, home_team_score, game_date
        FROM games
        ORDER BY game_date DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        game_id, away, home, away_score, home_score, date = row
        label = f"{away}_{away_score}_at_{home}_{home_score}_{date[:10]}"
        results.append((game_id, label))

    return results


def capture_game_screenshot(page, game_id: str, label: str, output_dir: Path) -> Path:
    """Capture screenshot for a specific game."""
    # Select the game in dropdown (by finding its index)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT game_id FROM games ORDER BY game_date DESC
    """)
    all_ids = [r[0] for r in cursor.fetchall()]
    conn.close()

    game_index = all_ids.index(game_id)

    # Navigate to dashboard
    page.goto(DASHBOARD_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(3)  # Wait for Streamlit to fully render

    # Find and click the selectbox
    selectbox = page.locator("div[data-testid='stSelectbox']")
    selectbox.click()
    time.sleep(1)

    # Get the dropdown listbox container
    listbox = page.locator("ul[role='listbox']")

    # Scroll down to make sure all options are rendered
    for _ in range(game_index // 5 + 1):
        listbox.evaluate("el => el.scrollTop += 200")
        time.sleep(0.2)

    time.sleep(0.5)

    # Try to find and click the option by text content
    # Get label text for this game from the games list
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT away_team_abbrev, home_team_abbrev, away_team_score, home_team_score
        FROM games WHERE game_id = ?
    """, (game_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        away, home, away_score, home_score = row
        # Match the format used in app.py
        option_text = f"{away} {away_score} @ {home} {home_score}"
        option = page.locator(f"li[role='option']:has-text('{option_text}')")
        option.click(timeout=10000)
    else:
        # Fallback to index-based selection
        options = page.locator("li[role='option']")
        options.nth(game_index).click(timeout=10000)

    time.sleep(2)  # Wait for data to load

    # Take screenshot
    output_path = output_dir / f"{label}.png"
    page.screenshot(path=str(output_path), full_page=True)

    return output_path


def main():
    print("=" * 60)
    print("NCAA Basketball Screenshot Capture")
    print("=" * 60)

    # Initialize
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    init_screenshots_table()

    # Get games
    games = get_game_ids()
    print(f"Found {len(games)} games total")

    # Check already captured
    already_captured = {f.stem for f in SCREENSHOTS_DIR.glob("*.png")}
    games_to_capture = [(gid, label) for gid, label in games if label not in already_captured]
    print(f"Already captured: {len(already_captured)}")
    print(f"Remaining to capture: {len(games_to_capture)}")

    if not games_to_capture:
        print("All screenshots already captured!")
        return

    viewport_width = 1920
    viewport_height = 1080

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": viewport_width, "height": viewport_height})

        captured = 0
        for game_id, label in games_to_capture:
            print(f"  Capturing {label}...", flush=True)
            try:
                path = capture_game_screenshot(page, game_id, label, SCREENSHOTS_DIR)
                store_screenshot_metadata(game_id, path, viewport_width, viewport_height)
                print(f"    Saved: {path.name}", flush=True)
                captured += 1
            except Exception as e:
                print(f"    ERROR: {e}", flush=True)

        browser.close()

    print(f"\n{'=' * 60}")
    print(f"Captured {captured}/{len(games_to_capture)} screenshots")
    print(f"Total screenshots: {len(already_captured) + captured}")
    print(f"Output directory: {SCREENSHOTS_DIR}")


if __name__ == "__main__":
    main()
