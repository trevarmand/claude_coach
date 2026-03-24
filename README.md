# Bike Training Coach

An AI-powered cycling coach built on [Claude Code](https://claude.com/claude-code). Drop in `.fit` files from your rides and get structured coaching analysis, recovery guidance, and training plans — all through conversation.

## How It Works

This project uses Claude Code as an interactive cycling coach. Your ride data (`.fit` files) and athlete profile live in this repo. When you start a conversation, Claude reads your profile and training history, then acts as a direct, data-driven coach.

### What it does

- **Ride analysis** — Parses `.fit` files for power, HR, cadence, speed, elevation, and temperature. Computes Normalized Power, Variability Index, and detects interval structures automatically.
- **Training log** — Maintains weekly summaries in markdown for quick trend review without re-parsing files.
- **Workout planning** — Builds structured plans with periodization based on your goals, schedule, and fitness level.
- **Recovery & fueling** — Advises on rest, active recovery, and nutrition around rides.

## Project Structure

```
athlete/              # Athlete profile (gitignored — personal data)
  profile.json        # Biometrics: height, weight, age, HR, FTP, VO2max
  preferences.json    # Units, coaching tone, analysis detail
  training.json       # Goals, schedule, indoor/outdoor, platform
  zones.json          # HR and power zone definitions
  lifestyle.json      # Sleep, cross-training, injuries

training_log/         # .fit files from rides, named MM-DD-YYYY (gitignored)
training_log_summary/ # Weekly markdown summaries (YYYY-WXX.md)
tools/
  parse_fit.py        # Python CLI to extract ride metrics as JSON
.claude/
  skills/             # Custom Claude Code skills (ride analysis, etc.)
```

## Setup

Requires Python 3 and the `fitparse` library.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fitparse
```

## Usage

1. **Start Claude Code** in this directory.
2. On first run, Claude walks through an onboarding interview to populate your athlete profile.
3. **Drop a `.fit` file** into `training_log/` (named `MM-DD-YYYY.fit`) and ask Claude to analyze it.
4. Ask for workout plans, recovery advice, or training history reviews.

### Example commands

- "Analyze my latest ride"
- "How was my ride on 03-23-2026?"
- "Build me a 3-week training plan for Zwift"
- "What should my recovery look like this week?"

## Parsing a ride manually

```bash
.venv/bin/python3 tools/parse_fit.py training_log/03-23-2026.fit
.venv/bin/python3 tools/parse_fit.py training_log/03-23-2026.fit --intervals
.venv/bin/python3 tools/parse_fit.py training_log/03-23-2026.fit --records
```

## Privacy

The `athlete/` directory and `.fit` files are gitignored. Only the tooling, summaries, and coach configuration are tracked.
