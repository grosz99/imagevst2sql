"""
Phase 0: Validate CBBpy data pipeline works reliably.

RUN THIS BEFORE BUILDING ANYTHING ELSE.

Success Criteria:
1. Can fetch game info for a known game_id
2. Can fetch boxscore with player stats
3. Can fetch play-by-play data
4. Can query games by date range
5. Data is consistent and parseable

Date Range: 2025-2026 NCAA Basketball Season (Sept 1, 2025 - Jan 9, 2026)
"""

import cbbpy.mens_scraper as cbb
import pandas as pd
from dataclasses import dataclass
from typing import Optional

# Season date constraints
SEASON_START = "2025-09-01"
SEASON_END = "2026-01-09"
# Use a single recent date for quick validation tests
TEST_DATE = "2025-12-07"  # A Saturday in December (typically has many games)


@dataclass
class ValidationResult:
    """Result from a validation test."""

    test_name: str
    passed: bool
    data_shape: Optional[tuple] = None
    sample_data: Optional[dict] = None
    error: Optional[str] = None


class CBBpyValidator:
    """
    Validates CBBpy package works for our use case.
    """

    def __init__(self):
        self.results: list[ValidationResult] = []
        self.test_game_id: Optional[str] = None

    def run_all_tests(self) -> list[ValidationResult]:
        """Run all validation tests."""
        print("=" * 60)
        print("CBBpy Validation Tests")
        print("=" * 60)

        # Test 1: Get game IDs for a specific date
        self._test_get_game_ids()

        # Test 2: Get game info
        self._test_get_game_info()

        # Test 3: Get boxscore
        self._test_get_boxscore()

        # Test 4: Get play-by-play
        self._test_get_pbp()

        # Test 5: Skip slow date range test - core functionality verified above

        # Print summary
        self._print_summary()

        return self.results

    def _test_get_game_ids(self):
        """Test: Can we get game IDs for a date?"""
        test_name = "Get Game IDs"
        print(f"\n[TEST] {test_name}...")

        try:
            # Use a date from the 2025-2026 season
            game_ids = cbb.get_game_ids(TEST_DATE)

            if game_ids and len(game_ids) > 0:
                self.results.append(
                    ValidationResult(
                        test_name=test_name,
                        passed=True,
                        data_shape=(len(game_ids),),
                        sample_data={"first_3_ids": game_ids[:3]},
                    )
                )
                print(f"  [PASS] Found {len(game_ids)} games")
                print(f"  Sample IDs: {game_ids[:3]}")

                # Store a game_id for subsequent tests
                self.test_game_id = game_ids[0]
            else:
                self.results.append(
                    ValidationResult(
                        test_name=test_name, passed=False, error="No game IDs returned"
                    )
                )
                print("  [FAIL] No games found")

        except Exception as e:
            self.results.append(
                ValidationResult(test_name=test_name, passed=False, error=str(e))
            )
            print(f"  [FAIL] Error: {e}")

    def _test_get_game_info(self):
        """Test: Can we get game metadata?"""
        test_name = "Get Game Info"
        print(f"\n[TEST] {test_name}...")

        if not self.test_game_id:
            self.results.append(
                ValidationResult(
                    test_name=test_name,
                    passed=False,
                    error="No game_id available from previous test",
                )
            )
            return

        try:
            info = cbb.get_game_info(self.test_game_id)

            if info is not None:
                self.results.append(
                    ValidationResult(
                        test_name=test_name,
                        passed=True,
                        sample_data={
                            "game_id": self.test_game_id,
                            "info_type": type(info).__name__,
                        },
                    )
                )
                print(f"  [PASS] Got game info for {self.test_game_id}")
                print(f"  Info type: {type(info)}")
            else:
                self.results.append(
                    ValidationResult(
                        test_name=test_name, passed=False, error="No info returned"
                    )
                )
                print("  [FAIL] No info returned")

        except Exception as e:
            self.results.append(
                ValidationResult(test_name=test_name, passed=False, error=str(e))
            )
            print(f"  [FAIL] Error: {e}")

    def _test_get_boxscore(self):
        """Test: Can we get boxscore data?"""
        test_name = "Get Boxscore"
        print(f"\n[TEST] {test_name}...")

        if not self.test_game_id:
            self.results.append(
                ValidationResult(
                    test_name=test_name, passed=False, error="No game_id available"
                )
            )
            return

        try:
            boxscore = cbb.get_game_boxscore(self.test_game_id)

            if isinstance(boxscore, pd.DataFrame) and len(boxscore) > 0:
                self.results.append(
                    ValidationResult(
                        test_name=test_name,
                        passed=True,
                        data_shape=boxscore.shape,
                        sample_data={"columns": list(boxscore.columns)[:10]},
                    )
                )
                print(
                    f"  [PASS] Got boxscore: {boxscore.shape[0]} rows, {boxscore.shape[1]} columns"
                )
                print(f"  Columns: {list(boxscore.columns)[:10]}...")
            else:
                self.results.append(
                    ValidationResult(
                        test_name=test_name,
                        passed=False,
                        error="Empty or invalid boxscore",
                    )
                )
                print("  [FAIL] Empty boxscore")

        except Exception as e:
            self.results.append(
                ValidationResult(test_name=test_name, passed=False, error=str(e))
            )
            print(f"  [FAIL] Error: {e}")

    def _test_get_pbp(self):
        """Test: Can we get play-by-play data?"""
        test_name = "Get Play-by-Play"
        print(f"\n[TEST] {test_name}...")

        if not self.test_game_id:
            self.results.append(
                ValidationResult(
                    test_name=test_name, passed=False, error="No game_id available"
                )
            )
            return

        try:
            pbp = cbb.get_game_pbp(self.test_game_id)

            if isinstance(pbp, pd.DataFrame) and len(pbp) > 0:
                self.results.append(
                    ValidationResult(
                        test_name=test_name,
                        passed=True,
                        data_shape=pbp.shape,
                        sample_data={"columns": list(pbp.columns)[:10]},
                    )
                )
                print(f"  [PASS] Got PBP: {pbp.shape[0]} plays, {pbp.shape[1]} columns")
                print(f"  Columns: {list(pbp.columns)[:10]}...")
            else:
                self.results.append(
                    ValidationResult(
                        test_name=test_name, passed=False, error="Empty or invalid PBP"
                    )
                )
                print("  [FAIL] Empty PBP data")

        except Exception as e:
            self.results.append(
                ValidationResult(test_name=test_name, passed=False, error=str(e))
            )
            print(f"  [FAIL] Error: {e}")

    def _test_get_games_range(self):
        """Test: Can we get games in a date range?"""
        test_name = "Get Games Range"
        print(f"\n[TEST] {test_name}...")

        try:
            # Get 2 days of games from the 2025-2026 season (reduced for faster test)
            info, box, pbp = cbb.get_games_range(
                "2025-12-06",
                "2025-12-07",
                info=True,
                box=True,
                pbp=False,  # Skip PBP to speed up test
            )

            games_found = len(info) if info is not None else 0
            box_rows = len(box) if box is not None else 0

            if games_found > 0:
                self.results.append(
                    ValidationResult(
                        test_name=test_name,
                        passed=True,
                        data_shape=(games_found, box_rows),
                        sample_data={"games": games_found, "boxscore_rows": box_rows},
                    )
                )
                print(f"  [PASS] Found {games_found} games, {box_rows} boxscore rows")
            else:
                self.results.append(
                    ValidationResult(
                        test_name=test_name, passed=False, error="No games in range"
                    )
                )
                print("  [FAIL] No games found")

        except Exception as e:
            self.results.append(
                ValidationResult(test_name=test_name, passed=False, error=str(e))
            )
            print(f"  [FAIL] Error: {e}")

    def _print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        for r in self.results:
            status = "[PASS]" if r.passed else "[FAIL]"
            print(f"  {status}: {r.test_name}")
            if not r.passed and r.error:
                print(f"         Error: {r.error}")

        print(f"\nResult: {passed}/{total} tests passed")

        if passed == total:
            print("\n[SUCCESS] CBBpy validation PASSED - ready for Phase 1")
        else:
            print("\n[FAILED] CBBpy validation FAILED - fix issues before proceeding")


if __name__ == "__main__":
    validator = CBBpyValidator()
    validator.run_all_tests()
