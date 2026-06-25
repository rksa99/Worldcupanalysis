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

```bash
# Generate today's dashboard (uses system date -> data/<date>.json)
python3 -m worldcup.cli

# A specific match day
python3 -m worldcup.cli --date 2026-06-25

# Write to a file instead of stdout
python3 -m worldcup.cli --date 2026-06-25 --out report.md

# Point at an explicit data file
python3 -m worldcup.cli --file path/to/day.json
```

No third-party dependencies — pure Python 3.10+ standard library.
A rendered example lives in [`reports/2026-06-25.md`](reports/2026-06-25.md).

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

## How it works

```
data/<date>.json ──> models ──> ┌─ odds (de-vig 1X2 -> fair probabilities)
                                 ├─ scores (Poisson xG -> top scorelines + W/D/L)
                                 ├─ incentives (final-matchday scenario solver)
                                 ├─ analysis (favorite, style, confidence, impact)
                                 └─ projections (projected final group tables)
                                          └─> dashboard (markdown render)
```

- **Probabilities** come from the aggregated 1X2 odds, with the bookmaker
  overround removed by proportional normalisation.
- **Scorelines** come from a Poisson model. If a match has odds but no authored
  expected goals, the model solves for the xG pair whose outcome split best
  matches the de-vigged market — so scores and probabilities stay consistent.
- **Incentives** are computed by enumerating every win/draw/loss combination of
  a group's remaining (final-matchday) fixtures and checking which of a team's
  own results still produce a top-two finish. Teams that can't reach the top two
  but can still finish 3rd are flagged as chasing a best-third place (the 2026
  format advances the eight best third-placed teams). Current goal difference is
  used as the tie-break; authored overrides in the data file always win.
- **Confidence** is High when the market favorite is also the side with the
  stronger incentive, Low when the price and the incentives pull apart.

### Limitations

The incentive solver reasons over match *results* (W/D/L) with current goal
difference frozen as the tie-break — it does not re-simulate goal difference
from today's predicted scores. For matchdays where qualification hinges on a
narrow goal-difference swing, treat the motivation label as indicative.

## Data format

One JSON file per day, `data/<date>.json`:

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

### Going live

`worldcup/data.py` is the only seam between the pipeline and its data source.
To run on real fixtures, replace `load_day` with a provider that pulls live
standings, results, head-to-head history, and aggregated sportsbook odds into
the same `DayData` model — every downstream module stays unchanged.

## Tests

```bash
python3 -m unittest discover -s tests
```
