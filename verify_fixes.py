#!/usr/bin/env python3
"""Verify two proposed fixes flagged by backtest_v33:
   (2) tighten the draw (Tipset) rule so it stops over-firing
   (3) the O/U 2.5 / total-goals Under bias
"""
import sys, math
sys.path.insert(0,"/sessions/festive-determined-hopper/mnt/.claude/skills/football-odds-model/scripts")
from match_model import score_matrix, elo_to_lambdas, summarise
from backtest_v33 import ELO,HOME,G,res

def lam(h_,a_,ho):
    return elo_to_lambdas(ELO[h_]+(HOME if ho else 0), ELO[a_])

# ---- (2) draw-rule variants: which threshold maximises W/D/L accuracy? ----
def tip(h,d,a,dmin,gate):
    if d>=dmin and max(h,a)<gate: return 1
    return 0 if h>a else 2
print("DRAW-RULE TUNING (W/D/L accuracy over 40 games; argmax baseline = 23 = 57%)")
print(f"{'draw>=':>7} {'gate<':>7} {'acc':>8} {'drawPicked':>11} {'drawHit':>8}")
best=None
for dmin in [0.26,0.28,0.30,0.32]:
    for gate in [0.42,0.45,0.48,0.52]:
        acc=picked=hit=0
        for h_,a_,hg,ag,ho in G:
            lh,la=lam(h_,a_,ho); P=score_matrix(lh,la,draw_boost=0.06)
            ph,pd,pa,_,_=summarise(P); r=res(hg,ag); t=tip(ph,pd,pa,dmin,gate)
            acc+=(t==r)
            if t==1: picked+=1; hit+=(r==1)
        print(f"{dmin:>7.2f} {gate:>7.2f} {acc:>3}/40={acc/40*100:>3.0f}% {picked:>11} {hit:>8}")

# ---- (3) O/U 2.5 bias: is total-goals level too low? sweep avg_goals ----
print("\nO/U 2.5 CALIBRATION vs total-goals level (avg_goals param)")
print("actual over(>=3) rate = 21/40 = 52.5%")
print(f"{'avg_goals':>9} {'meanP(over)':>12} {'Brier':>8} {'overPickAcc':>12}")
for ag_param in [2.6,2.8,3.0,3.2]:
    sp=br=acc=0.0
    for h_,a_,hg,ag,ho in G:
        lh,la=elo_to_lambdas(ELO[h_]+(HOME if ho else 0),ELO[a_],avg_goals=ag_param)
        P=score_matrix(lh,la,draw_boost=0.06)
        _,_,_,ov,_=summarise(P)
        actual=1 if (hg+ag)>=3 else 0
        sp+=ov; br+=(ov-actual)**2; acc+=((ov>=0.5)==actual)
    print(f"{ag_param:>9.1f} {sp/40*100:>11.1f}% {br/40:>8.4f} {acc:>3.0f}/40={acc/40*100:>3.0f}%")

# does draw_boost itself suppress overs? compare ov with/without boost at 2.6
print("\nDoes draw_boost suppress Over? (avg_goals=2.6)")
for db in [0.0,0.06]:
    sp=br=0.0
    for h_,a_,hg,ag,ho in G:
        lh,la=lam(h_,a_,ho); P=score_matrix(lh,la,draw_boost=db)
        _,_,_,ov,_=summarise(P); actual=1 if (hg+ag)>=3 else 0
        sp+=ov; br+=(ov-actual)**2
    print(f"  draw_boost={db}: meanP(over)={sp/40*100:.1f}%  Brier={br/40:.4f}")
