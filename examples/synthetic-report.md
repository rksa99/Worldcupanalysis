> **⚠️ SYNTHETIC DEMO** — generated from `examples/synthetic-day.json`, not real results.
> Run the app live (`--source live`, ESPN + The Odds API) for real numbers. See README.

# Daily World Cup Intelligence — 2026-06-25

_6 matches scheduled. Read each row in ~30 seconds: who is favored, why, what they need, expected behavior, likely scores, confidence, and qualification impact._

## Daily Match Intelligence Table

| Match | Group | Current Situation | Team Motivation | Market Favorite | Win Probabilities (H/D/A) | Most Likely Scores | Expected Style | Confidence | Projected Impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| South Korea vs South Africa | A | South Korea 2nd, South Africa 3rd. | South Korea: A draw is enough; South Africa: Must win (through in 100% of wins) | South Korea | 57% / 26% / 17% | 1-0, 2-0, 1-1 | Balanced game; favorite edges territory | Medium | South Korea advances in 83% of simulations. |
| Mexico vs Czechia | A | Mexico 1st, Czechia 4th. | Mexico: Already through; Czechia: Needs a win plus big swings elsewhere | Mexico | 62% / 23% / 15% | 1-0, 2-0, 1-1 | Balanced game; favorite edges territory | Medium | Mexico wins the group in 96% of simulations. |
| Germany vs Ecuador | E | Germany 1st, Ecuador 3rd. | Germany: Virtually through — advances in 97% even of losses; Ecuador: Must win (through in 48% of wins) | Germany | 65% / 22% / 13% | 1-0, 2-0, 1-1 | Must-win pressure — one side has to chase, opening the game | Low | Germany wins the group in 97% of simulations. |
| Senegal vs Qatar | E | Senegal 2nd, Qatar 4th. | Senegal: A draw is probably enough (87%); Qatar: Must win (through in 69% of wins) | Senegal | 60% / 24% / 16% | 1-0, 2-0, 1-1 | Balanced game; favorite edges territory | Medium | Senegal advances in 81% of simulations. |
| Brazil vs Croatia | F | Brazil 1st, Croatia 2nd. | Brazil: Already through; Croatia: A draw is enough | Brazil | 39% / 31% / 30% | 1-0, 0-0, 1-1 | Low-scoring tactical match | Medium | Brazil wins the group in 70% of simulations. |
| Nigeria vs Saudi Arabia | F | Nigeria 3rd, Saudi Arabia 4th. | Nigeria: Win and likely through (17%); Saudi Arabia: Needs a win plus big swings elsewhere | Near Even | 35% / 31% / 34% | 0-0, 1-0, 0-1 | Tight, evenly matched — fine margins decide | Low | Small margins — goal difference could decide. |

## Highest Confidence Favorites

| Rank | Team | Reason |
| --- | --- | --- |
| 1 | Mexico | 62% market edge; already through |
| 2 | Senegal | 60% market edge; a draw is probably enough (87%); advances in 81% of sims |
| 3 | South Korea | 57% market edge; a draw is enough; advances in 83% of sims |
| 4 | Brazil | 39% market edge; already through |

## Most Likely Draws

| Match | Reason |
| --- | --- |
| Nigeria vs Saudi Arabia | Evenly matched — fine margins |

## Chaos Matches

_Matches where incentives may cause unusual behavior._

| Match | Why |
| --- | --- |
| South Korea vs South Africa | One side must attack — asymmetric incentives open the game up |
| Germany vs Ecuador | One side must attack — asymmetric incentives open the game up |
| Senegal vs Qatar | One side must attack — asymmetric incentives open the game up |
| Nigeria vs Saudi Arabia | Too close to call — small events swing it |

## Projected Final Group Tables

_Only groups that play today. Points and goal difference are simulation averages; Top-2 is the qualification probability._

#### Group A

| Team | Proj. Points | Proj. GD | Top-2 | Status |
| --- | --- | --- | --- | --- |
| Mexico | 8.1 | +5.1 | 100% | Qualified |
| South Korea | 5 | +1.9 | 83% | Top-two in 83% |
| South Africa | 3.8 | -0.9 | 17% | Top-two in 17% |
| Czechia | 1.7 | -2.1 | 1% | Top-two in 1% |

#### Group E

| Team | Proj. Points | Proj. GD | Top-2 | Status |
| --- | --- | --- | --- | --- |
| Germany | 8.2 | +5.1 | 100% | Qualified |
| Senegal | 5.1 | +2 | 81% | Top-two in 81% |
| Ecuador | 3.6 | -1.1 | 9% | Top-two in 9% |
| Qatar | 1.7 | -3 | 11% | Top-two in 11% |

#### Group F

| Team | Proj. Points | Proj. GD | Top-2 | Status |
| --- | --- | --- | --- | --- |
| Brazil | 7.5 | +3.2 | 100% | Qualified |
| Croatia | 5.2 | +1.8 | 94% | Top-two in 94% |
| Nigeria | 2.4 | -0.9 | 6% | Top-two in 6% |
| Saudi Arabia | 2.3 | -4.1 | 0% | Eliminated |

_Model: 10,000 Monte Carlo simulations (seed 3923997243); data: file synthetic-day.json._
