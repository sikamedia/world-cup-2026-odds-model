#!/usr/bin/env python3
"""Head-to-head: v3.2 (skill default) vs v3.3 (all 3 fixes) over 40 games.
Confirms the combined fixes improve — and nothing regresses."""
import sys, math
SKILL="/sessions/festive-determined-hopper/mnt/.claude/skills/football-odds-model/scripts"
sys.path.insert(0, SKILL)
import match_model as v32                       # skill v3.2
sys.path.insert(0, "/sessions/festive-determined-hopper/mnt/world_cup_2026")
import match_model_v33 as v33                   # improved engine
from backtest_v33 import ELO, HOME, G, res

def metrics(engine, use_auto):
    n=len(G); acc=accrule=0; rps=ll=0.0
    draws_act=draw_prob=0.0; picked=0; blow_act=0; blow_exp=0.0; brier=0.0; ov_act=0
    DRAWGATE = getattr(engine, "DRAW_GATE", 0.52)
    for h_,a_,hg,ag,ho in G:
        eh=ELO[h_]+(HOME if ho else 0); ea=ELO[a_]
        lh,la=engine.elo_to_lambdas(eh,ea)
        style="balanced"
        if use_auto:
            style,_=engine.resolve_style("auto",(eh-ea))
        P=engine.score_matrix(lh,la,opp_style=style,draw_boost=0.06)
        h,d,a,ov,_=engine.summarise(P); r=res(hg,ag)
        acc += ((0 if h>a else 2)==r)
        pick = 1 if (d>=0.26 and max(h,a)<DRAWGATE) else (0 if h>a else 2)
        accrule += (pick==r)
        pc=[h,d,a]; oc=[1 if r==k else 0 for k in range(3)]
        cp=co=s=0.0
        for k in range(2): cp+=pc[k]; co+=oc[k]; s+=(cp-co)**2
        rps+=s/2
        ll+=math.log(max(P[(hg,ag)],1e-12))
        draw_prob+=d
        if r==1: draws_act+=1
        if pick==1: picked+=1
        if abs(hg-ag)>=3: blow_act+=1
        blow_exp+=sum(p for (i,j),p in P.items() if abs(i-j)>=3)
        actual_ov=1 if (hg+ag)>=3 else 0; ov_act+=actual_ov
        brier+=(ov-actual_ov)**2
    return dict(n=n,acc=acc,accrule=accrule,rps=rps/n,ll=ll,draw_prob=draw_prob/n,
                picked=picked,draws_act=draws_act,blow_act=blow_act,blow_exp=blow_exp,
                brier=brier/n,ov_act=ov_act)

A=metrics(v32, use_auto=False)   # v3.2: no auto-open, gate 0.52, avg_goals 2.6
B=metrics(v33, use_auto=True)    # v3.3: auto-open, gate 0.42, avg_goals 2.8

def row(name,k,fmt="{:.4f}",better="?"):
    av,bv=A[k],B[k]
    print(f"{name:34} {fmt.format(av):>10} {fmt.format(bv):>10}   {better}")

n=A["n"]
print("="*72)
print(f"v3.2 (skill default)  vs  v3.3 (all fixes)   — {n} completed matches")
print("="*72)
print(f"{'metric':34} {'v3.2':>10} {'v3.3':>10}")
print("-"*72)
print(f"{'W/D/L hard pick (argmax)':34} {A['acc']:>7}/40 {B['acc']:>7}/40   = {A['acc']/n*100:.0f}% / {B['acc']/n*100:.0f}%")
print(f"{'W/D/L with draw rule':34} {A['accrule']:>7}/40 {B['accrule']:>7}/40   = {A['accrule']/n*100:.0f}% / {B['accrule']/n*100:.0f}%  (FIX2)")
row("RPS (lower better)","rps","{:.4f}","FIX1 ↓ better")
row("Scoreline logL (higher better)","ll","{:.2f}","FIX1 ↑ better")
print(f"{'model avg draw %':34} {A['draw_prob']*100:>9.1f}% {B['draw_prob']*100:>9.1f}%   (actual 32.5%)")
print(f"{'draw rule fired (x)':34} {A['picked']:>10} {B['picked']:>10}   (FIX2: fewer false draws)")
print(f"{'blowout expected (actual 11)':34} {A['blow_exp']:>10.1f} {B['blow_exp']:>10.1f}   (FIX1 ↑)")
row("O/U 2.5 Brier (lower better)","brier","{:.4f}","FIX3 ↓ better")
print("-"*72)
print(f"actual: draws {A['draws_act']}/40, blowouts {A['blow_act']}, overs {A['ov_act']}/40")
print("\nAll three fixes combined: confirm RPS↓, logL↑, hard-pick↑, O/U Brier↓.")
