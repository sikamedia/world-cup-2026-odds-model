"""June-27 run: the 6 matchday-3 finales for Groups J, K, L (2026 WC).

These kick off the evening of Saturday June 27, 2026 (US Eastern), so at run
time they are UNPLAYED — this file carries fixtures + competition state +
weather only, for forward prediction. Results get appended next run.

Standings going into matchday 3 (reconstructed from MATCHES_54 batch 0/1/2):
  Group J: Argentina 6 (top, through), Austria 3 (GD 0), Algeria 3 (GD -2),
           Jordan 0 (out). Austria advances on a draw (head-to-head GD over
           Algeria); Algeria must win.
  Group K: Colombia 6 (through, top), Portugal 4 (through), DR Congo 1
           (must win to chase a best-third place), Uzbekistan 0 (out).
  Group L: England 4 & Ghana 4 (both effectively through, contest top spot),
           Croatia 3 (must beat Ghana to leapfrog), Panama 0 (out).

Fixtures / venues (ESPN + Yahoo + Ticketmaster, June 2026):
  Jordan-Argentina   AT&T Stadium, Arlington TX   (retractable roof -> AC)
  Algeria-Austria    Arrowhead, Kansas City MO    (open, warm evening)
  Colombia-Portugal  Hard Rock Stadium, Miami FL  (open, hot + humid)
  DR Congo-Uzbekistan Mercedes-Benz, Atlanta GA   (retractable roof -> AC)
  Panama-England     MetLife, East Rutherford NJ  (open, mild evening)
  Croatia-Ghana      Lincoln Financial, Phila PA  (open, warm 5pm)

Weather (world-weather.info / weather25 June-2026 outlook): Miami high 87-91F
humid (driest day of the month, low rain); Philadelphia/NJ corridor highs
74-93F, evening milder. Roofed venues are climate-controlled (heat=none).

Educational/analytical use only — not betting advice.
"""
from competition_state import MatchCompetitionState, SideCompetitionState, competition_state_payload
from match_context import context_key

# (home, away, host_home, heat, mot_home, mot_away, venue_note)
JUNE_27_MATCHES = [
    ("Jordan", "Argentina", 0, "none", "eliminated", "through",
     "Group J finale. AT&T Arlington (roof/AC). Jordan out (0pts); Argentina "
     "have clinched top spot (6pts) and may rotate."),
    ("Algeria", "Austria", 0, "mild", "mustwin", "normal",
     "Group J finale. Arrowhead KC (open, warm eve). Both 3pts for 2nd; "
     "Austria advances on a draw (GD), Algeria must win."),
    ("Colombia", "Portugal", 0, "moderate", "normal", "normal",
     "Group K finale. Hard Rock Miami (open, hot+humid ~30C eve). Both already "
     "through; contesting top spot, both may rotate."),
    ("DR Congo", "Uzbekistan", 0, "none", "mustwin", "eliminated",
     "Group K finale. Mercedes-Benz Atlanta (roof/AC). DR Congo (1pt) must win "
     "to chase a best-third berth; Uzbekistan out (0pts)."),
    ("Panama", "England", 0, "mild", "eliminated", "normal",
     "Group L finale. MetLife NJ (open, mild eve). Panama out (0pts); England "
     "(4pts) through, want top spot, slight rotation risk."),
    ("Croatia", "Ghana", 0, "mild", "mustwin", "normal",
     "Group L finale. Lincoln Financial Philadelphia (open, warm 5pm). Croatia "
     "(3pts) must win to overtake Ghana; Ghana (4pts) advance on a draw."),
]

JUNE_27_COMPETITION_STATE = {
    context_key("Jordan", "Argentina"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=0, mathematical_state="eliminated", stake_state="dead_rubber",
                rotation_risk="high", notes="out; nothing to play for"),
            away=SideCompetitionState(
                points=6, mathematical_state="qualified", stake_state="advance",
                rotation_risk="medium", notes="top spot clinched; likely rotation"),
        )
    ),
    context_key("Algeria", "Austria"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=3, mathematical_state="alive", stake_state="mustwin",
                rotation_risk="low", notes="must win for 2nd (GD -2)"),
            away=SideCompetitionState(
                points=3, mathematical_state="alive", stake_state="normal",
                rotation_risk="low", notes="advances on a draw via head-to-head GD"),
        )
    ),
    context_key("Colombia", "Portugal"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=6, mathematical_state="qualified", stake_state="top_spot",
                rotation_risk="medium", notes="through; leads group, light rotation"),
            away=SideCompetitionState(
                points=4, mathematical_state="qualified", stake_state="top_spot",
                rotation_risk="medium", notes="through; chasing top spot, light rotation"),
        )
    ),
    context_key("DR Congo", "Uzbekistan"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=1, mathematical_state="alive", stake_state="mustwin",
                rotation_risk="low", notes="must win to chase best-third"),
            away=SideCompetitionState(
                points=0, mathematical_state="eliminated", stake_state="dead_rubber",
                rotation_risk="high", notes="out"),
        )
    ),
    context_key("Panama", "England"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=0, mathematical_state="eliminated", stake_state="dead_rubber",
                rotation_risk="high", notes="out"),
            away=SideCompetitionState(
                points=4, mathematical_state="qualified", stake_state="top_spot",
                rotation_risk="medium", notes="through; want top spot, slight rotation"),
        )
    ),
    context_key("Croatia", "Ghana"): competition_state_payload(
        MatchCompetitionState(
            home=SideCompetitionState(
                points=3, mathematical_state="alive", stake_state="mustwin",
                rotation_risk="low", notes="must win to overtake Ghana"),
            away=SideCompetitionState(
                points=4, mathematical_state="alive", stake_state="normal",
                rotation_risk="low", notes="advances on a draw"),
        )
    ),
}
