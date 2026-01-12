# Product Requirements Document (PRD)
## Visual Context Layer: Image-First Analytical Agent

**Version:** 3.0  
**Author:** Justin  
**Date:** January 2026  
**Status:** Draft  

---

## 1. Executive Summary

Build a Visual Context Layer that uses dashboard/report screenshots as primary context for answering business questions. Based on research from DeepSeek's OCR paper (October 2025) suggesting visual representations may be 10x more token-efficient than text for LLM comprehension, this system creates a three-tier confidence cascade: Image Parsing → Verified Reports → SQL Generation.

**Core Hypothesis:** Screenshots encode priority, relationships, and business context (via layout, color, size, grouping) that semantic layers cannot capture in text form.

---

## 2. Phase 0: Validate Data Pipeline with CBBpy

**CRITICAL: Do this FIRST before building anything else.**

Before investing in the visual layer, validate that we can reliably get data using the **CBBpy** package for NCAA basketball. This proves out the data pipeline and gives us real content to test visual parsing against.

### 2.1 CBBpy Package Overview

CBBpy is a Python-based web scraper for NCAA basketball that bridges the gap between data and analysis for NCAA D1 basketball. It can grab play-by-play, boxscore, and other game metadata for any NCAA D1 men's or women's basketball game.

**Key Functions:**
- `get_game_info(game_id)` - game metadata (date, time, score, teams, referees)
- `get_game_boxscore(game_id)` - player stats as pandas DataFrame
- `get_game_pbp(game_id)` - play-by-play data
- `get_games_season(season)` - all games for a season
- `get_games_range(start_date, end_date)` - games in date range

### 2.2 Installation & Setup

```bash
# Create isolated environment
python -m venv venv_cbb
source venv_cbb/bin/activate  # Windows: venv_cbb\Scripts\activate

# Install CBBpy
pip install cbbpy

# Required dependencies (auto-installed)
# pandas>=2.0.0, numpy>=2.0.0, beautifulsoup4>=4.11.0, requests>=2.27.0
```

### 2.3 Validation Test Script

```python
# tests/validate_cbbpy.py
"""
Phase 0: Validate CBBpy data pipeline works reliably.

RUN THIS BEFORE BUILDING ANYTHING ELSE.

Success Criteria:
1. Can fetch game info for a known game_id
2. Can fetch boxscore with player stats
3. Can fetch play-by-play data
4. Can query games by date range
5. Data is consistent and parseable
"""

import cbbpy.mens_scraper as cbb
import pandas as pd
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


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
        
        # Test 5: Get games in date range
        self._test_get_games_range()
        
        # Print summary
        self._print_summary()
        
        return self.results
    
    def _test_get_game_ids(self):
        """Test: Can we get game IDs for a date?"""
        test_name = "Get Game IDs"
        print(f"\n[TEST] {test_name}...")
        
        try:
            # Use a date we know had games
            game_ids = cbb.get_game_ids("2024-12-07")
            
            if game_ids and len(game_ids) > 0:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=True,
                    data_shape=(len(game_ids),),
                    sample_data={"first_3_ids": game_ids[:3]}
                ))
                print(f"  ✓ Found {len(game_ids)} games")
                print(f"  Sample IDs: {game_ids[:3]}")
                
                # Store a game_id for subsequent tests
                self.test_game_id = game_ids[0]
            else:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=False,
                    error="No game IDs returned"
                ))
                print("  ✗ No games found")
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            ))
            print(f"  ✗ Error: {e}")
    
    def _test_get_game_info(self):
        """Test: Can we get game metadata?"""
        test_name = "Get Game Info"
        print(f"\n[TEST] {test_name}...")
        
        if not hasattr(self, 'test_game_id'):
            self.results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                error="No game_id available from previous test"
            ))
            return
        
        try:
            info = cbb.get_game_info(self.test_game_id)
            
            if info is not None:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=True,
                    sample_data={"game_id": self.test_game_id, "info_type": type(info).__name__}
                ))
                print(f"  ✓ Got game info for {self.test_game_id}")
                print(f"  Info type: {type(info)}")
            else:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=False,
                    error="No info returned"
                ))
                print("  ✗ No info returned")
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            ))
            print(f"  ✗ Error: {e}")
    
    def _test_get_boxscore(self):
        """Test: Can we get boxscore data?"""
        test_name = "Get Boxscore"
        print(f"\n[TEST] {test_name}...")
        
        if not hasattr(self, 'test_game_id'):
            self.results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                error="No game_id available"
            ))
            return
        
        try:
            boxscore = cbb.get_game_boxscore(self.test_game_id)
            
            if isinstance(boxscore, pd.DataFrame) and len(boxscore) > 0:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=True,
                    data_shape=boxscore.shape,
                    sample_data={"columns": list(boxscore.columns)[:10]}
                ))
                print(f"  ✓ Got boxscore: {boxscore.shape[0]} rows, {boxscore.shape[1]} columns")
                print(f"  Columns: {list(boxscore.columns)[:10]}...")
            else:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=False,
                    error="Empty or invalid boxscore"
                ))
                print("  ✗ Empty boxscore")
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            ))
            print(f"  ✗ Error: {e}")
    
    def _test_get_pbp(self):
        """Test: Can we get play-by-play data?"""
        test_name = "Get Play-by-Play"
        print(f"\n[TEST] {test_name}...")
        
        if not hasattr(self, 'test_game_id'):
            self.results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                error="No game_id available"
            ))
            return
        
        try:
            pbp = cbb.get_game_pbp(self.test_game_id)
            
            if isinstance(pbp, pd.DataFrame) and len(pbp) > 0:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=True,
                    data_shape=pbp.shape,
                    sample_data={"columns": list(pbp.columns)[:10]}
                ))
                print(f"  ✓ Got PBP: {pbp.shape[0]} plays, {pbp.shape[1]} columns")
                print(f"  Columns: {list(pbp.columns)[:10]}...")
            else:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=False,
                    error="Empty or invalid PBP"
                ))
                print("  ✗ Empty PBP data")
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            ))
            print(f"  ✗ Error: {e}")
    
    def _test_get_games_range(self):
        """Test: Can we get games in a date range?"""
        test_name = "Get Games Range"
        print(f"\n[TEST] {test_name}...")
        
        try:
            # Get 3 days of games
            info, box, pbp = cbb.get_games_range(
                "2024-12-05", 
                "2024-12-07",
                info=True,
                box=True,
                pbp=False  # Skip PBP to speed up test
            )
            
            games_found = len(info) if info is not None else 0
            box_rows = len(box) if box is not None else 0
            
            if games_found > 0:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=True,
                    data_shape=(games_found, box_rows),
                    sample_data={"games": games_found, "boxscore_rows": box_rows}
                ))
                print(f"  ✓ Found {games_found} games, {box_rows} boxscore rows")
            else:
                self.results.append(ValidationResult(
                    test_name=test_name,
                    passed=False,
                    error="No games in range"
                ))
                print("  ✗ No games found")
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name=test_name,
                passed=False,
                error=str(e)
            ))
            print(f"  ✗ Error: {e}")
    
    def _print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        for r in self.results:
            status = "✓ PASS" if r.passed else "✗ FAIL"
            print(f"  {status}: {r.test_name}")
            if not r.passed and r.error:
                print(f"         Error: {r.error}")
        
        print(f"\nResult: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n✓ CBBpy validation PASSED - ready for Phase 1")
        else:
            print("\n✗ CBBpy validation FAILED - fix issues before proceeding")


if __name__ == "__main__":
    validator = CBBpyValidator()
    validator.run_all_tests()
```

### 2.4 Success Criteria for Phase 0

| Test | Criteria | Status |
|------|----------|--------|
| Get Game IDs | Returns list of valid ESPN game IDs | ☐ |
| Get Game Info | Returns game metadata (teams, date, score) | ☐ |
| Get Boxscore | Returns DataFrame with player stats | ☐ |
| Get Play-by-Play | Returns DataFrame with game events | ☐ |
| Get Games Range | Can query multiple days of games | ☐ |

**Only proceed to Phase 1 if ALL tests pass.**

---

## 3. Claude Code Development Standards

### 3.1 CRITICAL: Pre-Implementation Checklist

Before writing ANY code, Claude Code MUST:

```bash
# 1. Search for existing functionality
rg "def capture" 
rg "class.*Agent"
rg "dashboard.*screenshot"

# 2. Check for similar file names
ls -la src/agents/
ls -la src/services/

# 3. Review existing models
rg "class.*BaseModel" --type py
```

### 3.2 File Structure (DO NOT DEVIATE)

```
visual-context-layer/
├── src/
│   ├── __init__.py
│   ├── models/                    # ALL Pydantic models here
│   │   ├── __init__.py
│   │   ├── dashboard.py           # Dashboard-related models
│   │   ├── responses.py           # API response models
│   │   ├── requests.py            # API request models
│   │   └── config.py              # Configuration models
│   ├── agents/                    # Agent implementations
│   │   ├── __init__.py
│   │   ├── visual_context.py      # Visual Context Agent
│   │   ├── orchestrator.py        # Main orchestrator
│   │   └── bi_interpreter.py      # BI interpretation agent
│   ├── services/                  # External service integrations
│   │   ├── __init__.py
│   │   ├── capture.py             # Screenshot capture service
│   │   ├── snowflake.py           # Snowflake operations
│   │   └── anthropic.py           # Claude API wrapper
│   ├── repositories/              # Data access layer
│   │   ├── __init__.py
│   │   └── dashboard_store.py     # Dashboard CRUD operations
│   └── utils/                     # Shared utilities
│       ├── __init__.py
│       ├── logging.py             # Structured logging
│       ├── security.py            # Security utilities
│       └── validation.py          # Custom validators
├── tests/
│   ├── __init__.py
│   ├── validate_cbbpy.py          # Phase 0 validation
│   ├── test_models.py
│   ├── test_agents.py
│   └── test_services.py
├── scripts/
│   └── setup_snowflake.sql        # Snowflake schema
├── pyproject.toml
├── CLAUDE.md                      # Claude Code instructions
└── README.md
```

### 3.3 Naming Conventions

```python
# ❌ NEVER create files like:
# visual_context_agent_v2.py
# capture_service_new.py
# dashboard_store_simplified.py

# ✅ ALWAYS use clear, single-purpose names:
# visual_context.py (the ONE visual context agent)
# capture.py (the ONE capture service)
```

---

## 4. Data Models (Pydantic v2 - MANDATORY)

### 4.1 Core Principle

**ABSOLUTE RULE**: Every structured data object MUST be a Pydantic model. No plain dictionaries for business logic.

```python
# ❌ NEVER DO THIS
def process_game(data: dict) -> dict:
    return {"game_id": data.get("id"), "score": data.get("score")}

# ✅ ALWAYS DO THIS
class GameResult(BaseModel):
    game_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    
def process_game(data: dict) -> GameResult:
    return GameResult(**data)  # Validation happens automatically
```

### 4.2 Configuration Models

```python
# src/models/config.py
"""
Application configuration with full validation.
NO FAKE DATA DEFAULTS - use proper configuration or fail explicitly.
"""

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class SnowflakeConfig(BaseModel):
    """Snowflake connection configuration."""
    
    account: str = Field(..., min_length=1)
    user: str = Field(..., min_length=1)
    password: SecretStr = Field(..., min_length=8)
    warehouse: str = Field(..., min_length=1)
    database: str = Field(..., min_length=1)
    schema_name: str = Field(alias="schema", min_length=1)
    
    model_config = {"extra": "forbid"}


class AnthropicConfig(BaseModel):
    """Anthropic API configuration."""
    
    api_key: SecretStr = Field(..., min_length=20)
    model: str = Field(default="claude-sonnet-4-20250514")
    max_tokens: int = Field(default=4096, ge=100, le=100000)
    
    model_config = {"extra": "forbid"}


class CaptureConfig(BaseModel):
    """Screenshot capture configuration."""
    
    viewport_width: int = Field(default=1920, ge=800, le=3840)
    viewport_height: int = Field(default=1080, ge=600, le=2160)
    wait_timeout_ms: int = Field(default=30000, ge=5000)
    render_delay_ms: int = Field(default=2000, ge=500)
    
    model_config = {"extra": "forbid"}


class Settings(BaseSettings):
    """
    Main application settings.
    CRITICAL: No fake defaults. Missing required config = explicit failure.
    """
    
    snowflake: SnowflakeConfig
    anthropic: AnthropicConfig
    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    
    visual_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    
    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__",
        "extra": "forbid"
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings. NEVER returns fake settings."""
    return Settings()
```

### 4.3 Response Models

```python
# src/models/responses.py
"""
API and agent response models.
"""

from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional
from enum import Enum


class ResponseSource(str, Enum):
    VISUAL = "visual_context"
    VERIFIED = "verified_report"
    GENERATED = "generated_sql"
    ERROR = "error"


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
    dashboard_id: Optional[str] = None
    dashboard_name: Optional[str] = None
    captured_at: Optional[datetime] = None
    missing_info: Optional[str] = None
    related_metrics: list[str] = Field(default_factory=list)
    
    @model_validator(mode='after')
    def validate_answer_confidence(self) -> 'VisualAgentResult':
        """Ensure answer is None when confidence is too low."""
        if self.confidence < 0.5 and self.answer is not None:
            raise ValueError(
                f'Answer must be None when confidence ({self.confidence}) < 0.5'
            )
        return self
    
    model_config = {"extra": "forbid"}


class AgentResponse(BaseModel):
    """Final response from the orchestrator."""
    
    answer: str = Field(..., min_length=1)
    source: ResponseSource
    confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    evidence: Optional[str] = None
    dashboard_reference: Optional[str] = None
    sql_query: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    processing_time_ms: Optional[int] = Field(default=None, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {"extra": "forbid"}
```

### 4.4 No Fake Data Policy

```python
# ❌ NEVER DO THIS: Fake data fallback
def get_game_stats(game_id: str) -> GameStats:
    try:
        stats = fetch_from_api(game_id)
        return stats
    except NotFound:
        # ❌ BAD: Returning fake data
        return GameStats(
            game_id=game_id,
            home_score=0,
            away_score=0,
            players=[]
        )

# ✅ ALWAYS DO THIS: Proper error handling
def get_game_stats(game_id: str) -> GameStats:
    try:
        stats = fetch_from_api(game_id)
        return stats
    except NotFound:
        # ✅ GOOD: Raise proper exception
        raise GameNotFoundError(f"Game {game_id} not found")
```

---

## 5. Architecture: Three-Tier Confidence Cascade

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CONFIDENCE CASCADE                              │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 1: Visual Context Agent                                      │
│  ├─ Input: Dashboard screenshots + user question                    │
│  ├─ Confidence: HIGHEST (human-validated visuals)                   │
│  ├─ Latency: <2s (no DB hit)                                        │
│  └─ Best for: "What should I focus on?" / "What's trending?"        │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 2: Verified Reports (Query Catalog)                          │
│  ├─ Input: Question → Stored procedure match                        │
│  ├─ Confidence: HIGH (pre-approved, deterministic)                  │
│  ├─ Latency: <3s (cached procs)                                     │
│  └─ Best for: "What's the Q3 variance?" / Standard reports          │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 3: SQL Generation                                            │
│  ├─ Input: Question → Generated query → Execution                   │
│  ├─ Confidence: MEDIUM (hallucination risk)                         │
│  ├─ Latency: 5-15s (generation + execution)                         │
│  └─ Best for: Novel analysis, ad-hoc exploration                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Utilities

### 6.1 Structured Logging (Security First)

```python
# src/utils/logging.py
"""
Structured logging with automatic sensitive data redaction.
"""

import logging
import json
from datetime import datetime


SENSITIVE_KEYS = {
    'password', 'token', 'api_key', 'secret', 
    'authorization', 'cookie', 'image_base64'
}


class StructuredFormatter(logging.Formatter):
    """JSON formatter that redacts sensitive data."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields, redacting sensitive ones
        for key, value in record.__dict__.items():
            if key.startswith('_') or key in (
                'name', 'msg', 'args', 'created', 'levelname'
            ):
                continue
            if any(s in key.lower() for s in SENSITIVE_KEYS):
                log_data[key] = "[REDACTED]"
            else:
                log_data[key] = value
        
        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    """Get configured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
```

---

## 7. CLAUDE.md for Claude Code

```markdown
# CLAUDE.md - Visual Context Layer

## Critical Rules

### 1. ALWAYS Use Pydantic Models
```python
# ❌ NEVER: def process(data: dict) -> dict
# ✅ ALWAYS: def process(data: dict) -> MyModel
```

### 2. NEVER Use Fake Data
```python
# ❌ NEVER: return User(id=0, name="Test")
# ✅ ALWAYS: raise NotFoundError("User not found")
```

### 3. Check Before Creating
```bash
rg "def function_name"
rg "class ClassName"
```

### 4. No Duplicate Files
Never create: agent_v2.py, service_new.py, handler_simplified.py

### 5. Security First
Never log sensitive data. Always use sanitize_for_logging().

## Commands
```bash
pytest tests/ -v          # Run tests
mypy src/                  # Type check
ruff check src/            # Lint
```
```

---

## 8. pyproject.toml

```toml
[project]
name = "visual-context-layer"
version = "0.1.0"
description = "Image-First Analytical Agent"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "cbbpy>=2.0.0",
    "pandas>=2.0.0",
    "snowflake-connector-python>=3.0.0",
    "playwright>=1.40.0",
    "httpx>=0.25.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "mypy>=1.8.0",
    "ruff>=0.2.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 9. Implementation Phases

### Phase 0: Validate CBBpy (Week 1)
- [ ] Run validation script
- [ ] Confirm all 5 tests pass
- [ ] Document any edge cases or rate limits
- [ ] Create sample dataset for testing

### Phase 1: Foundation (Week 2)
- [ ] Set up project structure exactly as specified
- [ ] Implement all Pydantic models with full validation
- [ ] Set up Snowflake schema
- [ ] Implement structured logging

### Phase 2: Capture Service (Week 3)
- [ ] Implement screenshot capture with Playwright
- [ ] Store screenshots in Snowflake
- [ ] Test with sample dashboards

### Phase 3: Visual Agent (Week 4)
- [ ] Implement VisualContextAgent
- [ ] Test with Claude Vision API
- [ ] Validate confidence thresholds

### Phase 4: Orchestrator (Week 5)
- [ ] Implement confidence cascade
- [ ] Add Layer 1 (Visual) routing
- [ ] Integration testing

---

## Appendix: Claude Code One-Shot Prompt

```
You are building a Visual Context Layer for analytics.

CRITICAL RULES:
1. Use Pydantic v2 models for ALL structured data - no plain dicts
2. NEVER use fake data fallbacks - raise proper exceptions
3. SEARCH codebase before creating any new files
4. NEVER create files like *_v2.py, *_new.py

START BY:
1. Running tests/validate_cbbpy.py to confirm data pipeline works
2. Creating pyproject.toml with all dependencies
3. Creating src/models/config.py with Settings class
4. Creating src/utils/logging.py with security redaction

TECH STACK:
- Python 3.11+
- Pydantic v2 + pydantic-settings  
- CBBpy for NCAA basketball data
- Anthropic SDK for Claude Vision
- Playwright for screenshots
- Ruff for linting (line-length=100)
```
