#!/usr/bin/env python3
"""Full backtest of football-odds-model on all 40 completed 2026 WC matches.

Predicts every played match PRE-MATCH with the model's actual v3.2 engine
(Elo -> lambda -> Poisson + Dixon-Coles + draw-boost), then compares to the
real result on:
  - W/D/L direction (argmax and draw-rule "Tipset" pick)
  - RPS (ranked probability score, ordered H/D/A)
  - log-loss of the actual scoreline (calibration of the score matrix)
  - draw-probability calibration
  - blowout (net>=3) calibration
  - O/U 2.5 calibration (Brier)
Then tests candidate improvements (draw-boost sweep, auto opp-style trigger).

Imports the LIVE skill engine so the backtest reflects exactly what the model
would output today. Educational/analytical use only.
"""
import sys, math
sys.path.insert(0, "/sessions/festive-determined-hopper/mnt/.claude/skills/football-odds-model/scripts")
from match_model import score_matrix, elo_to_lambdas, summarise

ELO = {
 "Mexico":1890,"South Africa":1720,"Korea":1785,"Czechia":1800,
 "Canada":1870,"Bosnia":1775,"Qatar":1640,"Switzerland":1891,
 "Brazil":1991,"Morocco":1860,"Haiti":1480,"Scotland":1780,
 "USA":1860,"Paraguay":1730,"Australia":1720,"Turkiye":1850,
 "Germany":1960,"Curacao":1500,"Cote dIvoire":1820,"Ecuador":1850,
 "Netherlands":1970,"Japan":1840,"Sweden":1810,"Tunisia":1720,
 "Belgium":1930,"Egypt":1628,"Iran":1810,"New Zealand":1500,
 "Spain":2157,"Cabo Verde":1620,"Saudi Arabia":1660,"Uruguay":1920,
 "France":2063,"Senegal":1880,"Iraq":1620,"Norway":1880,
 "Argentina":2115,"Algeria":1800,"Austria":1820,"Jordan":1640,
 "Portugal":1989,"DR Congo":1700,"Uzbekistan":1690,"Colombia":1982,
 "England":2024,"Croatia":1900,"Ghana":1750,"Panama":1640,
}
HOME = 85  # host-nation true-home Elo bump

# (home, away, hg, ag, host_home)  -- all 40 completed matches through Jun 21
G = [
 ("Mexico","South Africa",2,0,1),("Korea","Czechia",2,1,0),
 ("Mexico","Korea",1,0,1),("South Africa","Czechia",1,1,0),
 ("Qatar","Switzerland",1,1,0),("Canada","Bosnia",1,1,1),
 ("Switzerland","Bosnia",4,1,0),("Canada","Qatar",6,0,1),
 ("Brazil","Morocco",1,1,0),("Scotland","Haiti",1,0,0),
 ("Morocco","Scotland",1,0,0),("Brazil","Haiti",3,0,0),
 ("USA","Paraguay",4,1,1),("Australia","Turkiye",2,0,0),
 ("USA","Australia",2,0,1),("Paraguay","Turkiye",1,0,0),
 ("Germany","Curacao",7,1,0),("Cote dIvoire","Ecuador",1,0,0),
 ("Germany","Cote dIvoire",2,1,0),("Ecuador","Curacao",0,0,0),
 ("Netherlands","Japan",2,2,0),("Sweden","Tunisia",5,1,0),
 ("Netherlands","Sweden",5,1,0),("Japan","Tunisia",4,0,0),
 ("Belgium","Egypt",1,1,0),("Iran","New Zealand",2,2,0),
 ("Belgium","Iran",0,0,0),("New Zealand","Egypt",1,3,0),
 ("Spain","Cabo Verde",0,0,0),("Saudi Arabia","Uruguay",1,1,0),
 ("Spain","Saudi Arabia",4,0,0),("Uruguay","Cabo Verde",2,2,0),
 ("France","Senegal",3,1,0),("Norway","Iraq",4,1,0),
 ("Argentina","Algeria",3,0,0),("Austria","Jordan",3,1,0),
 ("Portugal","DR Congo",1,1,0),("Colombia","Uzbekistan",3,1,0),
 ("England","Croatia",4,2,0),("Ghana","Panama",1,0,0),
]

def res(hg,ag): return 0 if hg>ag else (1 if hg==ag else 2)  # H/D/A

def wdl_from_P(P):
    h,d,a,ov,btts = summarise(P)
    return h,d,a,ov

def tipset(h,d,a):
    if d>=0.26 and max(h,a)<0.52: return 1
    return 0 if h>a else 2

def rps_hda(probs, r):
    pc=list(probs); oc=[1 if r==k else 0 for k in range(3)]
    cp=co=s=0.0
    for k in range(2):
        cp+=pc[k]; co+=oc[k]; s+=(cp-co)**2
    return s/2

def run(draw_boost, auto_open=False, open_dElo=350):
    """Return aggregate metrics over all games for a config."""
    n=len(G)
    acc_argmax=acc_rule=0
    rps=ll=0.0
    draws_act=0; draw_prob_sum=0.0; draws_picked=0
    blow_act=0; blow_exp=0.0
    brier_ou=0.0; ou_act=0
    rows=[]
    for h_,a_,hg,ag,ho in G:
        lh,la = elo_to_lambdas(ELO[h_]+(HOME if ho else 0), ELO[a_])
        style="balanced"
        if auto_open and abs(ELO[h_]+(HOME if ho else 0)-ELO[a_])>=open_dElo:
            style="open"
        P=score_matrix(lh,la,opp_style=style,draw_boost=draw_boost)
        ph,pd,pa,pov=wdl_from_P(P)
        r=res(hg,ag)
        am=0 if ph>pa else 2
        acc_argmax+=(am==r)
        acc_rule+=(tipset(ph,pd,pa)==r)
        rps+=rps_hda((ph,pd,pa),r)
        ll+=math.log(max(P[(hg,ag)],1e-12))
        draw_prob_sum+=pd
        if r==1: draws_act+=1
        if tipset(ph,pd,pa)==1: draws_picked+=1
        if abs(hg-ag)>=3: blow_act+=1
        blow_exp+=sum(p for (i,j),p in P.items() if abs(i-j)>=3)
        # O/U 2.5
        actual_ov = 1 if (hg+ag)>=3 else 0
        ou_act+=actual_ov
        brier_ou+=(pov-actual_ov)**2
        # top scoreline
        top=max(P.items(),key=lambda x:x[1])
        rows.append((h_,a_,hg,ag,ph,pd,pa,pov,top[0],P[(hg,ag)],style))
    return dict(n=n,acc_argmax=acc_argmax,acc_rule=acc_rule,rps=rps/n,ll=ll,
                draws_act=draws_act,draw_prob=draw_prob_sum/n,draws_picked=draws_picked,
                blow_act=blow_act,blow_exp=blow_exp,brier_ou=brier_ou/n,ou_act=ou_act,
                rows=rows)

# ---------- per-match table (current default: draw_boost=0.06) ----------
base=run(0.06)
print("="*108)
print("PER-MATCH PREDICTIONS vs ACTUAL  (model v3.2 default: Elo+home Poisson+DC, draw_boost=0.06)")
print("="*108)
print(f"{'Match':38} {'Score':>6} {'pred WDL%':>16} {'pick':>4} {'topCS':>6} {'P(CS)':>6} {'O/U':>5} {'hit':>4}")
for (h_,a_,hg,ag,ph,pd,pa,pov,top,pcs,style) in base["rows"]:
    r=res(hg,ag)
    pk=tipset(ph,pd,pa); pkc={0:'1',1:'X',2:'2'}[pk]
    hit='OK' if pk==r else '.'
    actual_ov = (hg+ag)>=3
    ou_pred = 'O' if pov>=0.5 else 'U'
    ou_hit = '' if (ou_pred=='O')==actual_ov else '*'
    print(f"{h_+' v '+a_:38} {str(hg)+'-'+str(ag):>6} "
          f"{ph*100:4.0f}/{pd*100:3.0f}/{pa*100:3.0f}   {pkc:>2} {hit:>2} "
          f"{str(top[0])+'-'+str(top[1]):>6} {pcs*100:5.1f} {ou_pred}{ou_hit:>2} ")

print("\n"+"="*70)
print("AGGREGATE BACKTEST METRICS (current default draw_boost=0.06)")
print("="*70)
n=base["n"]
print(f"Games: {n}")
print(f"W/D/L  argmax (H/A only)     : {base['acc_argmax']}/{n} = {base['acc_argmax']/n*100:.0f}%")
print(f"W/D/L  with draw rule (Tipset): {base['acc_rule']}/{n} = {base['acc_rule']/n*100:.0f}%")
print(f"RPS (avg, lower=better)       : {base['rps']:.4f}")
print(f"Scoreline total log-likelihood: {base['ll']:.2f}  (avg {base['ll']/n:.3f})")
print(f"Draws  actual {base['draws_act']}/{n} = {base['draws_act']/n*100:.1f}%  |"
      f"  model avg draw prob {base['draw_prob']*100:.1f}%  | rule picked draw {base['draws_picked']}x")
print(f"Blowouts (net>=3) actual {base['blow_act']}  | model expected {base['blow_exp']:.1f}")
print(f"O/U2.5 Brier {base['brier_ou']:.4f}  | actual over rate {base['ou_act']}/{n} = {base['ou_act']/n*100:.0f}%")

# ---------- improvement test 1: draw-boost sweep ----------
print("\n"+"="*70)
print("IMPROVEMENT TEST 1 - draw-boost sweep (RPS + scoreline logL)")
print("="*70)
print(f"{'draw_boost':>10} {'RPS':>8} {'logL':>9} {'modelDraw%':>11} {'WDLrule':>8}")
for db in [0.0,0.03,0.06,0.09,0.12,0.15]:
    r=run(db)
    print(f"{db:>10.2f} {r['rps']:>8.4f} {r['ll']:>9.2f} {r['draw_prob']*100:>10.1f}% "
          f"{r['acc_rule']}/{n:>3}")

# ---------- improvement test 2: auto opp-style open on large Elo gap ----------
print("\n"+"="*70)
print("IMPROVEMENT TEST 2 - auto-trigger --opp-style open when ΔElo>=threshold")
print("(does systematic blowout-tail fattening help scoreline logL & blowout fit?)")
print("="*70)
print(f"{'rule':>26} {'logL':>9} {'blowExp':>8} {'blowAct':>8} {'RPS':>8}")
r0=run(0.06,auto_open=False)
print(f"{'default (no auto-open)':>26} {r0['ll']:>9.2f} {r0['blow_exp']:>8.1f} {r0['blow_act']:>8} {r0['rps']:>8.4f}")
for thr in [450,400,350,300,250]:
    r=run(0.06,auto_open=True,open_dElo=thr)
    print(f"{'auto-open ΔElo>='+str(thr):>26} {r['ll']:>9.2f} {r['blow_exp']:>8.1f} {r['blow_act']:>8} {r['rps']:>8.4f}")

# ---------- biggest scoreline misses (lowest P on actual) ----------
print("\n"+"="*70)
print("WORST-CALIBRATED SCORELINES (lowest model P on the actual result)")
print("="*70)
worst=sorted(base["rows"],key=lambda x:x[9])[:8]
for (h_,a_,hg,ag,ph,pd,pa,pov,top,pcs,style) in worst:
    print(f"  {h_+' v '+a_:34} actual {hg}-{ag}  P(actual)={pcs*100:4.1f}%  "
          f"(model top {top[0]}-{top[1]})")
