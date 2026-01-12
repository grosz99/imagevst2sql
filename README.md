# NCAA Basketball Analytics - Visual Context Agent

A Streamlit chatbot that uses three competing agents to answer questions about NCAA basketball games:

1. **Visual Context Agent** - Analyzes dashboard screenshots using Claude Vision
2. **Semantic Layer** - Matches questions to pre-defined verified SQL queries
3. **SQL Generation** - Generates dynamic SQL queries using an LLM

All three agents race in parallel to answer your question. See which one is fastest and most accurate!

## Demo

Ask questions like:
- "Who scored the most points for Duke?"
- "Who had the most assists for UVA?"
- "What was the score of the Wake Forest game?"
- "Which team won by the biggest margin?"

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your API key

Create a `.env` file:
```
ANTHROPIC_API_KEY=your_key_here
```

Or enter it in the sidebar when running the app.

### 3. Run the chatbot

```bash
streamlit run chatbot.py
```

## Project Structure

```
├── chatbot.py              # Main competition mode chatbot
├── app.py                  # Dashboard for viewing boxscores
├── data/
│   ├── ncaa_basketball.db  # SQLite database (37 games, 1145 players)
│   └── screenshots/        # Game boxscore screenshots
├── src/
│   ├── agents/
│   │   ├── visual_context.py   # Claude Vision agent
│   │   ├── semantic_layer.py   # Pre-defined query matcher
│   │   └── orchestrator.py     # Agent orchestration
│   ├── services/
│   │   └── anthropic.py        # Anthropic API wrapper
│   └── models/                 # Pydantic models
├── scripts/
│   ├── cbbscrapter.py          # ESPN data scraper
│   └── capture_screenshots.py  # Screenshot automation
└── requirements.txt
```

## How It Works

### Visual Context Agent
- Finds screenshots matching teams mentioned in your question
- Sends the screenshot to Claude Vision for analysis
- Best for questions about specific games with screenshots

### Semantic Layer
- Pattern-matches your question to pre-defined SQL queries
- No LLM call needed - fastest response time
- Best for common questions (top scorer, most assists, etc.)

### SQL Generation Agent
- Uses an LLM to generate custom SQL queries
- Most flexible but slower
- Best for complex or unusual questions

## Deployment

This repo is configured for Streamlit Cloud:

1. Fork/clone this repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set main file to `chatbot.py`
5. Add `ANTHROPIC_API_KEY` in Secrets

## Data

- **37 games** from ESPN NCAA basketball
- **1,145 player stats** with points, assists, rebounds, etc.
- **10 game screenshots** for visual context

## License

MIT
