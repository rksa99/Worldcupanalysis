# Daily World Cup Intelligence

Every morning, generate **one dashboard** covering all matches scheduled that
day. The goal: a reader understands each match in ~30 seconds —

- Who is favored
- Why they are favored
- What each team needs
- Expected game behavior
- Most likely scores
- Confidence level
- Impact on qualification
- Projected final group standings

## Quick start

The app is **live by default** — it pulls real fixtures, results and standings
from ESPN's public API and real betting odds from The Odds API.

```bash
# Today's dashboard from live data (ESPN + odds)
python3 -m worldcup.cli

# A specific match day, live
python3 -m worldcup.cli --date 2026-06-25

# Enable multi-sportsbook consensus odds (recommended)
export ODDS_API_KEY=your_key_from_the-odds-api.com
python3 -m worldcup.cli --date 2026-06-25 --out report.md --cache

# Offline / demo from a JSON file
python3 -m worldcup.cli --source file --file examples/synthetic-day.json

# Machine-readable output, custom simulation depth
python3 -m worldcup.cli --format json --sims 50000 --seed 1
```

No third-party dependencies — pure Python 3.10+ standard library.
A rendered (synthetic) example lives in
[`examples/synthetic-report.md`](examples/synthetic-report.md).

### Live data sources

| Data | Source | Key needed |
| --- | --- | --- |
| Fixtures, results, standings | ESPN public API (`site.api.espn.com`, league `fifa.world`) | No |
| Betting odds (multi-book consensus) | [The Odds API](https://the-odds-api.com) | `ODDS_API_KEY` |
| Betting odds (fallback) | ESPN embedded odds | No |

When `ODDS_API_KEY` is set, odds are the average h2h decimal price across all
US/UK/EU books The Odds API returns. Without it, ESPN's embedded line is used
where available; otherwise probabilities fall back to the scoreline model.

> **Network requirement.** The hosts above must be reachable from wherever the
> app runs. Some managed/CI sandboxes (including the one this repo may have been
> generated in) restrict outbound egress and will block these hosts with a 403
> — run on a normal network, or allowlist `site.api.espn.com` and
> `api.the-odds-api.com`. Use `--source auto` to fall back to a cached
> `data/<date>.json` when live fetch is unavailable, and `--cache` to write one.

### Modes (`--source`)

- `auto` (default): try live, fall back to a cached `data/<date>.json`.
- `live`: live only; error out if a source is unreachable.
- `file`: read a specific JSON file (`--file`) — for offline use and demos.

## Output

The dashboard contains:

1. **Daily Match Intelligence Table** — one row per match with all columns above.
2. **Highest Confidence Favorites** — ranked safest picks of the day.
3. **Most Likely Draws** — matches leaning to a stalemate.
4. **Chaos Matches** — where incentives may cause unusual behavior.
5. **Projected Final Group Tables** — for every group playing today.

### Column definitions

| Column | Meaning |
| --- | --- |
| Match | Home vs Away |
| Group | Group letter |
| Current Situation | One-sentence standings summary |
| Team Motivation | Each side's key incentive (must win / draw enough / qualified / …) |
| Market Favorite | Favored team, or `Near Even` |
| Win Probabilities | Home / Draw / Away, de-vigged from odds |
| Most Likely Scores | Top three scorelines |
| Expected Style | Short football read on how the game plays |
| Confidence | High (market + incentives agree), Medium, Low (they conflict) |
| Projected Impact | One-sentence qualification consequence |

## Architecture

Data flows one way through small, single-purpose layers:

```
sources/  espn.py (fixtures/results/standings)   filesource.py (offline/cache)
          oddsapi.py (multi-book consensus)      names.py, http.py
              │
              ▼
domain.py   DayData — the one vocabulary every layer speaks
              │
              ▼
markets.py  de-vig 1X2 odds -> fair probabilities
poisson.py  per-match scoreline probability matrix (xG calibrated to market)
              │
              ▼
simulate.py Monte Carlo group simulator — the single engine
              │
              ▼
narrative.py labels backed by simulated probabilities
report.py    typed DailyReport (plain data)
              │
              ▼
render.py    markdown | JSON   (add renderers without touching the engine)
```

### The engine

One **Monte Carlo simulation** (default 10,000 runs per group, `--sims`)
answers every question the dashboard asks, from a single source of truth:

- **Scorelines** are sampled from each match's Poisson matrix. When a match has
  market odds but no authored xG, the matrix is calibrated so its win/draw/loss
  split matches the de-vigged market — scores, probabilities, and simulations
  always agree.
- **Team motivation** comes from *conditional* qualification probabilities
  measured inside the simulation: P(top two | win), P(top two | draw),
  P(top two | loss). "Must win (through in 92% of wins)" is a measured number,
  not a heuristic. Goal difference is simulated per run — never frozen.
- **Projected tables** show simulation-average points and goal difference plus
  each team's top-two probability, so uncertainty is visible instead of a
  single assumed result.
- **Projected impact** cites the simulation directly ("advances in 83% of
  simulations"), and **confidence** is High when the market favorite is also
  the side with the stronger incentive, Low when price and incentives conflict.
- Runs are **reproducible**: the seed defaults to a value derived from the date
  (same morning, same report), or pass `--seed`.

Win probabilities in the main table come from the aggregated 1X2 odds with the
bookmaker overround removed by proportional normalisation; the Poisson model is
the fallback when no odds exist. Authored `motivation`/`situation` overrides in
a data file always win over generated labels.

### Limitations

- Group tie-breaks are modelled as points → goal difference → goals for →
  random; FIFA's head-to-head and fair-play criteria are not modelled.
- Best-third qualification is flagged per group but not resolved across all
  twelve groups (that needs every group's data, not just today's).
- Probabilities inherit whatever bias the betting market has.

## Data format (file mode / cache)

Live runs need no files. For offline use, demos, or the `--cache` snapshot the
app reads/writes one JSON file per day (`data/<date>.json`):

```json
{
  "date": "2026-06-25",
  "groups": {
    "A": {
      "standings": [
        {"team": "Mexico", "played": 2, "won": 2, "drawn": 0, "lost": 0, "gf": 5, "ga": 1}
      ]
    }
  },
  "matches": [
    {
      "home": "South Korea", "away": "South Africa", "group": "A",
      "kickoff": "2026-06-25T16:00:00Z",
      "odds": {"home": 1.65, "draw": 3.70, "away": 5.50},
      "xg": {"home": 1.4, "away": 0.8},
      "h2h": "Korea unbeaten in last 3",
      "situation": "Optional authored override sentence",
      "motivation": {"home": "A draw is enough", "away": "Must win"}
    }
  ]
}
```

`odds` and `xg` are optional but recommended; `xg` is derived from `odds` when
omitted. `situation` and `motivation` override the engine when present.

### Adding another live source

`worldcup/sources/` holds the live integrations (one module per source). To add
one (e.g. api-football, football-data.org), parse its response into the domain
models and compose it in `sources.load_live` — every downstream module stays
unchanged.

## Daily automation

Run it each morning with cron and post/save the result, e.g.:

```cron
0 7 * * *  ODDS_API_KEY=xxxx /usr/bin/python3 -m worldcup.cli --cache \
           --out /var/www/worldcup/$(date +\%F).md
```

## Tests

```bash
python3 -m unittest discover -s tests
```
