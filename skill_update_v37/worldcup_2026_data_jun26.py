"""June-26 run extension: 54 prior games + 6 resolved June-25 matchday-3 games
(Groups D/E/F) = 60 played matches. Adds JUNE_26_MATCHES fixtures to predict
and reserves the June-26 result batch for the next 66-game backtest.

June-25 results (batch 4, out-of-sample for v3.6, which was tuned on 54):
  Group D: USA 2-3 Turkiye, Paraguay 0-0 Australia
  Group E: Curacao 0-2 Cote dIvoire, Ecuador 2-1 Germany
  Group F: Japan 1-1 Sweden, Tunisia 1-3 Netherlands
Source: ESPN / Yahoo Sports / FIFA live scores (June 2026).
Educational/analytical use only — not betting advice.
"""
from competition_state import MatchCompetitionState, SideCompetitionState, competition_state_payload
from match_context import context_key
from worldcup_2026_data import ELO, HOME, MATCHES_54

# (home, away, hg, ag, host_home, batch) — batch 4 = Jun25 oos for v3.6
JUNE_25_RESULTS = [
    ("USA", "Turkiye", 2, 3, 1, 4),
    ("Paraguay", "Australia", 0, 0, 0, 4),
    ("Curacao", "Cote dIvoire", 0, 2, 0, 4),
    ("Ecuador", "Germany", 2, 1, 0, 4),
    ("Japan", "Sweden", 1, 1, 0, 4),
    ("Tunisia", "Netherlands", 1, 3, 0, 4),
]

MATCHES_60 = MATCHES_54 + JUNE_25_RESULTS

# Fill this only after final scores are confirmed from a reliable source.
# (home, away, hg, ag, host_home, batch) — batch 5 = Jun26 oos for v3.7.
JUNE_26_RESULTS = [
    # ("Norway", "France", hg, ag, 0, 5),
    # ("Senegal", "Iraq", hg, ag, 0, 5),
    # ("Uruguay", "Spain", hg, ag, 0, 5),
    # ("Cabo Verde", "Saudi Arabia", hg, ag, 0, 5),
    # ("Egypt", "Iran", hg, ag, 0, 5),
    # ("New Zealand", "Belgium", hg, ag, 0, 5),
]

MATCHES_66 = MATCHES_60 + JUNE_26_RESULTS

# June-26 matchday-3 finales to PREDICT.
# (home, away, host_home, heat, mot_home, mot_away, venue_note)
# heat/weather scales set after pulling match-day forecast (see report).
JUNE_26_MATCHES = [
    ("Norway", "France", 0, "none", "normal", "normal",
     "Gillette, Foxborough MA, 3pm ET. Both already through (6pts); playing for "
     "group top spot. France may rest a few; Norway full intensity for #1 seed."),
    ("Senegal", "Iraq", 0, "none", "eliminated", "eliminated",
     "BMO Field, Toronto, 3pm ET. Both eliminated (0pts) — dead rubber, rotation/pride."),
    ("Uruguay", "Spain", 0, "none", "mustwin", "through",
     "Estadio Akron, Guadalajara (~1566m altitude), 8pm local. Uruguay (2pts) must "
     "win to advance; Spain (4pts) effectively through, may rotate."),
    ("Cabo Verde", "Saudi Arabia", 0, "none", "mustwin", "mustwin",
     "NRG Stadium, Houston (retractable roof, AC — weather neutral), 8pm ET. "
     "Cabo Verde (2pts) vs Saudi (1pt), winner can sneak through."),
    ("Egypt", "Iran", 0, "none", "normal", "mustwin",
     "Lumen Field, Seattle (temperate, mild), 11pm ET/8pm PT. Egypt (4pts) tops group, "
     "a draw likely enough; Iran (2pts) must win. Note: Iran higher Elo than Egypt."),
    ("New Zealand", "Belgium", 0, "none", "eliminated", "mustwin",
     "BC Place, Vancouver (indoor roof — weather neutral), 11pm ET/8pm PT. "
     "Belgium (2pts) must win to advance; NZ (1pt) all but out."),
]

JUNE_26_COMPETITION_STATE = {
    context_key("Norway", "France"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=6,
                mathematical_state="qualified",
                stake_state="top_spot",
                rotation_risk="low",
                notes="already through; playing for group top spot",
            ),
            away=SideCompetitionState(
                points=6,
                mathematical_state="qualified",
                stake_state="top_spot",
                rotation_risk="medium",
                notes="already through; possible partial rotation while chasing top spot",
            ),
        )
    ),
    context_key("Senegal", "Iraq"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=0,
                mathematical_state="eliminated",
                stake_state="dead_rubber",
                rotation_risk="high",
                notes="eliminated dead rubber",
            ),
            away=SideCompetitionState(
                points=0,
                mathematical_state="eliminated",
                stake_state="dead_rubber",
                rotation_risk="high",
                notes="eliminated dead rubber",
            ),
        )
    ),
    context_key("Uruguay", "Spain"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=2,
                mathematical_state="alive",
                stake_state="mustwin",
                rotation_risk="low",
                notes="must win to advance",
            ),
            away=SideCompetitionState(
                points=4,
                mathematical_state="qualified",
                stake_state="advance",
                rotation_risk="medium",
                notes="effectively through; rotation risk",
            ),
        )
    ),
    context_key("Cabo Verde", "Saudi Arabia"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=2,
                mathematical_state="alive",
                stake_state="mustwin",
                rotation_risk="low",
                notes="winner can advance",
            ),
            away=SideCompetitionState(
                points=1,
                mathematical_state="alive",
                stake_state="mustwin",
                rotation_risk="low",
                notes="must win to stay alive",
            ),
        )
    ),
    context_key("Egypt", "Iran"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=4,
                mathematical_state="alive",
                stake_state="advance",
                rotation_risk="low",
                notes="draw likely enough but not modeled as fully qualified",
            ),
            away=SideCompetitionState(
                points=2,
                mathematical_state="alive",
                stake_state="mustwin",
                rotation_risk="low",
                notes="must win to advance",
            ),
        )
    ),
    context_key("New Zealand", "Belgium"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=1,
                mathematical_state="eliminated",
                stake_state="dead_rubber",
                rotation_risk="high",
                notes="all but out; treated as eliminated for rotation risk",
            ),
            away=SideCompetitionState(
                points=2,
                mathematical_state="alive",
                stake_state="mustwin",
                rotation_risk="low",
                notes="must win to advance",
            ),
        )
    ),
}
