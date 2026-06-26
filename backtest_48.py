#!/usr/bin/env python3
"""Football-odds-model backtest — ALL 48 completed 2026 WC matches (through Jun 23).

Extends backtest_44.py with the 4 Group K/L matchday-2 games played Jun 23
(Portugal-Uzbekistan, Colombia-DR Congo, England-Ghana, Panama-Croatia).
Those 4 are a genuine OUT-OF-SAMPLE test of v3.4, whose key fix (gd_per_100 0.55)
was tuned on the prior 44. We report:
  (a) full-48 metrics for v3.2 / v3.3 / v3.4,
  (b) the 4 new Jun-23 games in isolation (out-of-sample for v3.4),
  (c) candidate v3.5 improvement sweeps on the full 48.

Self-contained. Engine math identical to match_model_v34.py.
Educational/analytical use only — not betting advice.
"""
import math

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
HOME = 85

# (home, away, hg, ag, host_home, batch)  batch: 0=orig40, 1=Jun22(oos v3.3), 2=Jun23(oos v3.4)
G = [
 ("Mexico","South Africa",2,0,1,0),("Korea","Czechia",2,1,0,0),
 ("Mexico","Korea",1,0,1,0),("South Africa","Czechia",1,1,0,0),
 ("Qatar","Switzerland",1,1,0,0),("Canada","Bosnia",1,1,1,0),
 ("Switzerland","Bosnia",4,1,0,0),("Canada","Qatar",6,0,1,0),
 ("Brazil","Morocco",1,1,0,0),("Scotland","Haiti",1,0,0,0),
 ("Morocco","Scotland",1,0,0,0),("Brazil","Haiti",3,0,0,0),
 ("USA","Paraguay",4,1,1,0),("Australia","Turkiye",2,0,0,0),
 ("USA","Australia",2,0,1,0),("Paraguay","Turkiye",1,0,0,0),
 ("Germany","Curacao",7,1,0,0),("Cote dIvoire","Ecuador",1,0,0,0),
 ("Germany","Cote dIvoire",2,1,0,0),("Ecuador","Curacao",0,0,0,0),
 ("Netherlands","Japan",2,2,0,0),("Sweden","Tunisia",5,1,0,0),
 ("Netherlands","Sweden",5,1,0,0),("Japan","Tunisia",4,0,0,0),
 ("Belgium","Egypt",1,1,0,0),("Iran","New Zealand",2,2,0,0),
 ("Belgium","Iran",0,0,0,0),("New Zealand","Egypt",1,3,0,0),
 ("Spain","Cabo Verde",0,0,0,0),("Saudi Arabia","Uruguay",1,1,0,0),
 ("Spain","Saudi Arabia",4,0,0,0),("Uruguay","Cabo Verde",2,2,0,0),
 ("France","Senegal",3,1,0,0),("Norway","Iraq",4,1,0,0),
 ("Argentina","Algeria",3,0,0,0),("Austria","Jordan",3,1,0,0),
 ("Portugal","DR Congo",1,1,0,0),("Colombia","Uzbekistan",3,1,0,0),
 ("England","Croatia",4,2,0,0),("Ghana","Panama",1,0,0,0),
 # ---- 4 games (Jun 22), out-of-sample for v3.3 ----
 ("France","Iraq",3,0,0,1),("Norway","Senegal",3,2,0,1),
 ("Argentina","Austria",2,0,0,1),("Algeria","Jordan",2,1,0,1),
 # ---- 4 NEW games (Jun 23), out-of-sample for v3.4 ----
 ("Portugal","Uzbekistan",5,0,0,2),("Colombia","DR Congo",1,0,0,2),
 ("England","Ghana",0,0,0,2),("Panama","Croatia",0,1,0,2),
]

def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)

def negbin(k, mu, r):
    p = r / (r + mu)
    return (math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1))
            * p**r * (1-p)**k)

def dc_tau(i, j, lh, la, rho):
    if i==0 and j==0: return 1 - lh*la*rho
    if i==0 and j==1: return 1 + lh*rho
    if i==1 and j==0: return 1 + la*rho
    if i==1 and j==1: return 1 - rho
    return 1.0

def score_matrix(lh, la, n=11, rho=-0.05, opp_style="balanced", disp=5.0,
                 draw_boost=0.06):
    fav_home = lh >= la
    def marg(k, lam, is_fav):
        if opp_style=="open" and is_fav: return negbin(k, lam, disp)
        return pois(k, lam)
    P, tot = {}, 0.0
    for i in range(n):
        for j in range(n):
            p = marg(i,lh,fav_home)*marg(j,la,not fav_home)*dc_tau(i,j,lh,la,rho)
            P[(i,j)] = p; tot += p
    P = {k: v/tot for k,v in P.items()}
    if draw_boost > 0:
        d = sum(p for (i,j),p in P.items() if i==j)
        if 0 < d < 1:
            td = min(0.97, d+draw_boost); fd, fo = td/d, (1-td)/(1-d)
            P = {(i,j): p*(fd if i==j else fo) for (i,j),p in P.items()}
    return P

def elo_to_lambdas(elo_h, elo_a, home_bump=0.0, avg_goals=2.8, gd_per_100=0.45):
    d = (elo_h+home_bump) - elo_a
    gd = d/100.0 * gd_per_100
    base = avg_goals/2.0
    return max(0.15, base+gd/2), max(0.15, base-gd/2)

def summarise(P):
    h=d=a=ov=btts=0.0
    for (i,j),p in P.items():
        if i>j: h+=p
        elif i==j: d+=p
        else: a+=p
        if i+j>=3: ov+=p
        if i>=1 and j>=1: btts+=p
    return h,d,a,ov,btts

def predict(h_, a_, ho, cfg):
    eh = ELO[h_] + (HOME if ho else 0)
    ea = ELO[a_]
    lh, la = elo_to_lambdas(eh, ea, avg_goals=cfg["avg_goals"],
                            gd_per_100=cfg.get("gd_per_100",0.45))
    gap = eh - ea
    style = "balanced"
    if cfg["auto_open"] and abs(gap) >= cfg["open_delo"]:
        style = "open"
    P = score_matrix(lh, la, opp_style=style, draw_boost=cfg["draw_boost"])
    ph,pd,pa,pov,_ = summarise(P)
    return ph,pd,pa,pov,P

def res(hg,ag): return 0 if hg>ag else (1 if hg==ag else 2)

def rps_hda(probs, r):
    pc=list(probs); oc=[1 if r==k else 0 for k in range(3)]
    cp=co=s=0.0
    for k in range(2):
        cp+=pc[k]; co+=oc[k]; s+=(cp-co)**2
    return s/2

def tipset(h,d,a,gate):
    if d>=0.26 and max(h,a)<gate: return 1
    return 0 if h>a else 2

def metrics(games, cfg):
    n=len(games)
    acc_hada=acc_rule=acc_arg3=0
    rps=ll=0.0
    draws_act=0; dps=0.0; draws_picked=0
    blow_act=0; blow_exp=0.0
    brier_ou=0.0; ou_act=0
    rows=[]
    for h_,a_,hg,ag,ho,new in games:
        ph,pd,pa,pov,P = predict(h_,a_,ho,cfg)
        r=res(hg,ag)
        am = 0 if ph>pa else 2
        arg3 = max(range(3), key=lambda k:[ph,pd,pa][k])
        acc_hada += (am==r)
        acc_arg3 += (arg3==r)
        acc_rule += (tipset(ph,pd,pa,cfg["draw_gate"])==r)
        rps += rps_hda((ph,pd,pa), r)
        ll += math.log(max(P[(hg,ag)],1e-12))
        dps += pd
        if r==1: draws_act+=1
        if tipset(ph,pd,pa,cfg["draw_gate"])==1: draws_picked+=1
        if abs(hg-ag)>=3: blow_act+=1
        blow_exp += sum(p for (i,j),p in P.items() if abs(i-j)>=3)
        actual_ov = 1 if (hg+ag)>=3 else 0
        ou_act += actual_ov
        brier_ou += (pov-actual_ov)**2
        top=max(P.items(),key=lambda x:x[1])
        rows.append((h_,a_,hg,ag,ph,pd,pa,pov,top[0],P[(hg,ag)],new))
    return dict(n=n,acc_hada=acc_hada,acc_arg3=acc_arg3,acc_rule=acc_rule,
                rps=rps/n,ll=ll,draws_act=draws_act,draw_prob=dps/n,
                draws_picked=draws_picked,blow_act=blow_act,blow_exp=blow_exp,
                brier_ou=brier_ou/n,ou_act=ou_act,rows=rows)

V32 = dict(avg_goals=2.6, auto_open=False, open_delo=300, draw_boost=0.06, draw_gate=0.52, gd_per_100=0.45)
V33 = dict(avg_goals=2.8, auto_open=True,  open_delo=300, draw_boost=0.06, draw_gate=0.42, gd_per_100=0.45)
V34 = dict(avg_goals=2.85,auto_open=True,  open_delo=300, draw_boost=0.07, draw_gate=0.42, gd_per_100=0.55)

def show(title, m):
    n=m["n"]
    print(f"\n{'='*64}\n{title}  (n={n})\n{'='*64}")
    print(f"W/D/L argmax H/A-only  : {m['acc_hada']}/{n} = {m['acc_hada']/n*100:.0f}%")
    print(f"W/D/L true 3-way argmax: {m['acc_arg3']}/{n} = {m['acc_arg3']/n*100:.0f}%")
    print(f"W/D/L Tipset(draw rule): {m['acc_rule']}/{n} = {m['acc_rule']/n*100:.0f}%  (picked X {m['draws_picked']}x)")
    print(f"RPS (lower better)     : {m['rps']:.4f}")
    print(f"Scoreline logL (sum)   : {m['ll']:.2f}  (avg {m['ll']/n:.3f})")
    print(f"Draws actual {m['draws_act']}/{n}={m['draws_act']/n*100:.1f}% | model avg draw {m['draw_prob']*100:.1f}%")
    print(f"Blowout net>=3 actual {m['blow_act']} | model exp {m['blow_exp']:.1f}")
    print(f"O/U2.5 Brier {m['brier_ou']:.4f} | actual over {m['ou_act']}/{n}={m['ou_act']/n*100:.0f}%")

allg = G
new4 = [g for g in G if g[5]==2]   # Jun-23, out-of-sample for v3.4

print("#"*64)
print("# PART 1 — v3.2 / v3.3 / v3.4 on the FULL 48 played matches")
print("#"*64)
show("v3.2 (avg 2.6, no auto-open, gate .52, gd .45) — FULL 48", metrics(allg,V32))
show("v3.3 (avg 2.8, auto>=300, gate .42, gd .45) — FULL 48", metrics(allg,V33))
show("v3.4 (avg 2.85, auto>=300, gate .42, gd .55, db .07) — FULL 48", metrics(allg,V34))

print("\n"+"#"*64)
print("# PART 2 — OUT-OF-SAMPLE: the 4 new Jun-23 games only")
print("#   (v3.4's gd=0.55 fix was tuned on the prior 44; honest test)")
print("#"*64)
mN33=metrics(new4,V33); mN34=metrics(new4,V34)
print("\nPer-match (v3.4 pre-match prediction):")
print(f"{'Match':28}{'Score':>6}{'  H/D/A model%':>18}{'  argmax':>8}{'topCS':>7}{'P(act)':>8}{'O/U':>5}")
for (h_,a_,hg,ag,ph,pd,pa,pov,top,pact,new) in mN34["rows"]:
    r=res(hg,ag); arg3=max(range(3),key=lambda k:[ph,pd,pa][k])
    hit='OK' if arg3==r else 'X'
    oupred='O' if pov>=.5 else 'U'; ouhit='ok' if ((hg+ag)>=3)==(pov>=.5) else 'X'
    print(f"{h_+' v '+a_:28}{str(hg)+'-'+str(ag):>6}{ph*100:6.0f}/{pd*100:3.0f}/{pa*100:3.0f}%"
          f"{hit:>8}{str(top[0])+'-'+str(top[1]):>7}{pact*100:7.1f}%{oupred+'/'+ouhit:>6}")
show("v3.3 — NEW 4 (Jun23) only", mN33)
show("v3.4 — NEW 4 (Jun23) only", mN34)

print("\n"+"#"*64)
print("# PART 3 — candidate v3.5 sweeps on FULL 48 (vs v3.4 baseline)")
print("#"*64)

print("\n[3a] gd_per_100 sweep (re-confirm 0.55 optimum on 48)")
print(f"{'gd/100':>10}{'RPS':>9}{'logL':>9}{'modelDraw%':>12}{'blowExp':>9}")
for gd in [0.45,0.50,0.55,0.60,0.65,0.70]:
    c=dict(V34); c["gd_per_100"]=gd; m=metrics(allg,c)
    print(f"{gd:>10.2f}{m['rps']:>9.4f}{m['ll']:>9.2f}{m['draw_prob']*100:>11.1f}%{m['blow_exp']:>9.1f}")

print("\n[3b] draw_boost sweep (model draw vs actual)")
print(f"{'draw_boost':>10}{'RPS':>9}{'logL':>9}{'modelDraw%':>12}")
for db in [0.04,0.06,0.07,0.09,0.12]:
    c=dict(V34); c["draw_boost"]=db; m=metrics(allg,c)
    print(f"{db:>10.2f}{m['rps']:>9.4f}{m['ll']:>9.2f}{m['draw_prob']*100:>11.1f}%")

print("\n[3c] avg_goals sweep (O/U 2.5 Brier)")
print(f"{'avg_goals':>10}{'P(over)avg':>12}{'Brier':>9}{'RPS':>9}")
for ag_ in [2.7,2.8,2.85,2.9,3.0,3.1]:
    c=dict(V34); c["avg_goals"]=ag_; m=metrics(allg,c)
    povavg=sum(row[7] for row in m["rows"])/m["n"]
    print(f"{ag_:>10.2f}{povavg*100:>11.1f}%{m['brier_ou']:>9.4f}{m['rps']:>9.4f}")

print("\n[3d] auto-open ΔElo threshold sweep (blowout tail)")
print(f"{'thresh':>10}{'logL':>9}{'blowExp':>9}{'blowAct':>9}{'RPS':>9}")
for thr in [99999,400,350,300,250,200]:
    c=dict(V34); c["open_delo"]=thr; c["auto_open"]=(thr<99999); m=metrics(allg,c)
    lab="off" if thr==99999 else str(thr)
    print(f"{lab:>10}{m['ll']:>9.2f}{m['blow_exp']:>9.1f}{m['blow_act']:>9}{m['rps']:>9.4f}")

print("\n[3e] worst-calibrated scorelines (lowest model P on actual), v3.4 full-48")
worst=sorted(metrics(allg,V34)["rows"], key=lambda x:x[9])[:12]
for (h_,a_,hg,ag,ph,pd,pa,pov,top,pact,new) in worst:
    tag={0:'',1:' [oos-Jun22]',2:' [oos-Jun23]'}[new]
    print(f"  {h_+' v '+a_:30} {hg}-{ag}  P(act)={pact*100:4.1f}%  model-top {top[0]}-{top[1]}{tag}")
print("\nEducational/analytical use only — not betting advice.")
