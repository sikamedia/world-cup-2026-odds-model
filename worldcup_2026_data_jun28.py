"""June-28 run extension: 66 played games + 6 resolved June-27 matchday-3
finales (Groups J/K/L) = 72 played group-stage matches. Round of 32 begins
June 28 (single match: South Africa vs Canada).

June-27 results (batch 6, out-of-sample for v3.7A, which was tuned on 66):
  Group J: Jordan 1-3 Argentina (Messi 19th WC goal, 7th straight game scoring),
           Algeria 3-3 Austria (wild draw; BOTH advance, Iran knocked out).
  Group K: Colombia 0-0 Portugal (Colombia top group), DR Congo 3-1 Uzbekistan
           (DR Congo grab a Round-of-32 berth as a best third).
  Group L: Panama 0-2 England (Kane 11th WC goal, England top group),
           Croatia 2-1 Ghana (Croatia finish runner-up).

Sources: Olympics.com / Yahoo Sports / CBS / NBC live scores, June 27-28 2026.
Educational/analytical use only - not betting advice.
"""
from competition_state import MatchCompetitionState, SideCompetitionState, competition_state_payload
from match_context import context_key
from worldcup_2026_data import ELO, HOME
from worldcup_2026_data_jun26 import MATCHES_66

# (home, away, hg, ag, host_home, batch) - batch 6 = Jun27 oos for v3.7A
JUNE_27_RESULTS = [
    ("Jordan", "Argentina", 1, 3, 0, 6),
    ("Algeria", "Austria", 3, 3, 0, 6),
    ("Colombia", "Portugal", 0, 0, 0, 6),
    ("DR Congo", "Uzbekistan", 3, 1, 0, 6),
    ("Panama", "England", 0, 2, 0, 6),
    ("Croatia", "Ghana", 2, 1, 0, 6),
]

MATCHES_72 = MATCHES_66 + JUNE_27_RESULTS

# Round of 32 - June 28 (the only KO game today).
# (home, away, host_home, heat, mot_home, mot_away, venue_note)
# Knockout => both sides full-intensity (win-or-go-home), neutral venue.
JUNE_28_MATCHES = [
    ("South Africa", "Canada", 0, "none", "normal", "normal",
     "Round of 32. SoFi Stadium, Los Angeles (fixed translucent roof -> "
     "climate-controlled, heat=none). Win-or-go-home, both full strength. "
     "South Africa 2nd in Group A (beat Korea, lost to Mexico); Canada 2nd in "
     "Group B (drew Bosnia, hammered Qatar 6-0, lost to Switzerland)."),
]

JUNE_28_COMPETITION_STATE = {
    context_key("South Africa", "Canada"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=0, mathematical_state="alive", stake_state="mustwin",
                rotation_risk="low", notes="knockout - win or out"),
            away=SideCompetitionState(
                points=0, mathematical_state="alive", stake_state="mustwin",
                rotation_risk="low", notes="knockout - win or out"),
        )
    ),
}
