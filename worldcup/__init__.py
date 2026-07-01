"""Daily World Cup Intelligence.

Generate a single morning dashboard covering every match scheduled for a day:
who is favored, why, what each team needs, expected game behavior, most likely
scores, confidence, qualification impact, and projected final group tables.

Architecture (data flows one way):

    sources/ (ESPN, The Odds API, file)  ->  domain.DayData
        -> markets (de-vig)  +  poisson (score matrices)
        -> simulate (Monte Carlo group simulator)
        -> narrative (labels backed by simulated probabilities)
        -> report (typed DailyReport)
        -> render (markdown / JSON)
"""

__version__ = "2.0.0"
