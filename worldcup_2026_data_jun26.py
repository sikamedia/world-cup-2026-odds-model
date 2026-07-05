"""June-26 run extension: 54 prior games + 6 resolved June-25 matchday-3 games
(Groups D/E/F) = 60 played matches, plus the 6 resolved June-26 matchday-3
finals (Groups G/H/I) = 66 played matches.

June-25 results (batch 4, out-of-sample for v3.6, which was tuned on 54):
  Group D: USA 2-3 Turkiye, Paraguay 0-0 Australia
  Group E: Curacao 0-2 Cote dIvoire, Ecuador 2-1 Germany
  Group F: Japan 1-1 Sweden, Tunisia 1-3 Netherlands

June-26 results (batch 5, out-of-sample for v3.7):
  Group I: France 4-1 Norway (Dembele hat-trick; France win the group, Norway
           rotated heavily), Senegal 5-0 Iraq (Iraq down to 10 men)
  Group H: Spain 4-0 Saudi Arabia, Uruguay 2-2 Cabo Verde
  Group G: Iran 0-0 Belgium, Egypt 3-1 New Zealand (Egypt's first WC win)

FIXTURE CORRECTION: an earlier draft of JUNE_26_MATCHES mis-paired Groups H and
G (Uruguay-Spain / CaboVerde-Saudi / Egypt-Iran / NZ-Belgium). Those pairings
did not occur. The real matchday-3 pairings are used here (Spain-Saudi /
Uruguay-CaboVerde / Iran-Belgium / Egypt-NZ).

Sources: ESPN FIFA World Cup 2026 MD11 recap; Wikipedia 2026 FIFA World Cup
Group I (ESPN/Yahoo/FIFA live scores, June 2026).
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

# Confirmed June-26 finals (batch 5 = Jun26 oos for v3.7). Real matchday-3
# pairings; same home/away order as JUNE_26_MATCHES so context_keys line up.
# (home, away, hg, ag, host_home, batch)
JUNE_26_RESULTS = [
    ("Norway", "France", 1, 4, 0, 5),
    ("Senegal", "Iraq", 5, 0, 0, 5),
    ("Spain", "Saudi Arabia", 4, 0, 0, 5),
    ("Uruguay", "Cabo Verde", 2, 2, 0, 5),
    ("Iran", "Belgium", 0, 0, 0, 5),
    ("Egypt", "New Zealand", 3, 1, 0, 5),
]

MATCHES_66 = MATCHES_60 + JUNE_26_RESULTS

# June-26 matchday-3 finals (real pairings). Neutral venues (host_home=0).
# (home, away, host_home, heat, mot_home, mot_away, venue_note)
JUNE_26_MATCHES = [
    ("Norway", "France", 0, "none", "normal", "normal",
     "Group I finale. Both already through (6pts), playing for top spot. "
     "In reality France fielded a strong XI and Norway rotated heavily."),
    ("Senegal", "Iraq", 0, "none", "eliminated", "eliminated",
     "Group I finale. Both eliminated (0pts) — dead rubber."),
    ("Spain", "Saudi Arabia", 0, "none", "through", "mustwin",
     "Group H finale. Spain (4pts) effectively through, may rotate; "
     "Saudi Arabia (1pt) must win for any chance."),
    ("Uruguay", "Cabo Verde", 0, "none", "mustwin", "mustwin",
     "Group H finale. Uruguay (2pts) and Cabo Verde (2pts) both need a result "
     "to advance."),
    ("Iran", "Belgium", 0, "none", "mustwin", "mustwin",
     "Group G finale. Iran (2pts) and Belgium (2pts) both must win to advance."),
    ("Egypt", "New Zealand", 0, "none", "normal", "eliminated",
     "Group G finale. Egypt (4pts) tops the group, a draw likely enough; "
     "New Zealand (1pt) all but out."),
]

JUNE_26_COMPETITION_STATE = {
    context_key("Norway", "France"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=6,
                mathematical_state="qualified",
                stake_state="top_spot",
                rotation_risk="medium",
                notes="already through; rotated heavily in reality",
            ),
            away=SideCompetitionState(
                points=6,
                mathematical_state="qualified",
                stake_state="top_spot",
                rotation_risk="low",
                notes="already through; chasing top spot with a strong XI",
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
    context_key("Spain", "Saudi Arabia"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=4,
                mathematical_state="qualified",
                stake_state="advance",
                rotation_risk="medium",
                notes="effectively through; rotation risk",
            ),
            away=SideCompetitionState(
                points=1,
                mathematical_state="alive",
                stake_state="mustwin",
                rotation_risk="low",
                notes="must win for any chance",
            ),
        )
    ),
    context_key("Uruguay", "Cabo Verde"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=2,
                mathematical_state="alive",
                stake_state="mustwin",
                rotation_risk="low",
                notes="needs a result to advance",
            ),
            away=SideCompetitionState(
                points=2,
                mathematical_state="alive",
                stake_state="mustwin",
                rotation_risk="low",
                notes="needs a result to advance",
            ),
        )
    ),
    context_key("Iran", "Belgium"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=2,
                mathematical_state="alive",
                stake_state="mustwin",
                rotation_risk="low",
                notes="must win to advance",
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
    context_key("Egypt", "New Zealand"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=4,
                mathematical_state="alive",
                stake_state="advance",
                rotation_risk="low",
                notes="tops the group; a draw likely enough",
            ),
            away=SideCompetitionState(
                points=1,
                mathematical_state="eliminated",
                stake_state="dead_rubber",
                rotation_risk="high",
                notes="all but out; treated as eliminated",
            ),
        )
    ),
}
