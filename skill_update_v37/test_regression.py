#!/usr/bin/env python3
"""Regression test for the v3.7 football-odds-model bundle core.

Imports the PATCHED match_model.py in this package and re-runs the engine over
all 54 played 2026 WC matches (through Jun 24). Locks the v3.6A backtest numbers
so an accidental edit to the defaults is caught immediately.

This regression covers the core engine only. The market-context CSV/JSON pipeline
is documented in SKILL.md and INSTALL.md and has its own regression test.

Run:  python3 test_regression.py
Expect: "ALL v3.6 REGRESSION CHECKS PASSED".
Educational/analytical use only — not betting advice.
"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))
import match_model as mm

# Confirm the patched module-level defaults are actually v3.6 ----------------
import inspect
src = inspect.getsource(mm.elo_to_lambdas)
assert "avg_goals=2.90" in src and "gd_per_100=0.65" in src, "elo_to_lambdas defaults are not v3.6"
assert "draw_boost=0.06" in inspect.getsource(mm.score_matrix), "score_matrix draw_boost is not 0.06"

ELO = {
 "Mexico":1890,"South Africa":1720,"Korea":1785,"Czechia":1800,"Canada":1870,
 "Bosnia":1775,"Qatar":1640,"Switzerland":1891,"Brazil":1991,"Morocco":1860,
 "Haiti":1480,"Scotland":1780,"USA":1860,"Paraguay":1730,"Australia":1720,
 "Turkiye":1850,"Germany":1960,"Curacao":1500,"Cote dIvoire":1820,"Ecuador":1850,
 "Netherlands":1970,"Japan":1840,"Sweden":1810,"Tunisia":1720,"Belgium":1930,
 "Egypt":1628,"Iran":1810,"New Zealand":1500,"Spain":2157,"Cabo Verde":1620,
 "Saudi Arabia":1660,"Uruguay":1920,"France":2063,"Senegal":1880,"Iraq":1620,
 "Norway":1880,"Argentina":2115,"Algeria":1800,"Austria":1820,"Jordan":1640,
 "Portugal":1989,"DR Congo":1700,"Uzbekistan":1690,"Colombia":1982,"England":2024,
 "Croatia":1900,"Ghana":1750,"Panama":1640,
}
HOME = 85
G = [
 ("Mexico","South Africa",2,0,1),("Korea","Czechia",2,1,0),("Mexico","Korea",1,0,1),
 ("South Africa","Czechia",1,1,0),("Qatar","Switzerland",1,1,0),("Canada","Bosnia",1,1,1),
 ("Switzerland","Bosnia",4,1,0),("Canada","Qatar",6,0,1),("Brazil","Morocco",1,1,0),
 ("Scotland","Haiti",1,0,0),("Morocco","Scotland",1,0,0),("Brazil","Haiti",3,0,0),
 ("USA","Paraguay",4,1,1),("Australia","Turkiye",2,0,0),("USA","Australia",2,0,1),
 ("Paraguay","Turkiye",1,0,0),("Germany","Curacao",7,1,0),("Cote dIvoire","Ecuador",1,0,0),
 ("Germany","Cote dIvoire",2,1,0),("Ecuador","Curacao",0,0,0),("Netherlands","Japan",2,2,0),
 ("Sweden","Tunisia",5,1,0),("Netherlands","Sweden",5,1,0),("Japan","Tunisia",4,0,0),
 ("Belgium","Egypt",1,1,0),("Iran","New Zealand",2,2,0),("Belgium","Iran",0,0,0),
 ("New Zealand","Egypt",1,3,0),("Spain","Cabo Verde",0,0,0),("Saudi Arabia","Uruguay",1,1,0),
 ("Spain","Saudi Arabia",4,0,0),("Uruguay","Cabo Verde",2,2,0),("France","Senegal",3,1,0),
 ("Norway","Iraq",4,1,0),("Argentina","Algeria",3,0,0),("Austria","Jordan",3,1,0),
 ("Portugal","DR Congo",1,1,0),("Colombia","Uzbekistan",3,1,0),("England","Croatia",4,2,0),
 ("Ghana","Panama",1,0,0),("France","Iraq",3,0,0),("Norway","Senegal",3,2,0),
 ("Argentina","Austria",2,0,0),("Algeria","Jordan",2,1,0),("Portugal","Uzbekistan",5,0,0),
 ("Colombia","DR Congo",1,0,0),("England","Ghana",0,0,0),("Panama","Croatia",0,1,0),
 ("Mexico","Czechia",3,0,1),("South Africa","Korea",1,0,0),("Canada","Switzerland",1,3,1),
 ("Bosnia","Qatar",3,1,0),("Brazil","Scotland",3,0,0),("Morocco","Haiti",4,2,0),
]

def res(hg,ag): return 0 if hg>ag else (1 if hg==ag else 2)
def rps(p,r):
    o=[1 if r==k else 0 for k in range(3)]; cp=co=s=0.0
    for k in range(2): cp+=p[k]; co+=o[k]; s+=(cp-co)**2
    return s/2

n=len(G); dirhit=0; rsum=0.0; dps=0.0; blow=0.0
for h,a,hg,ag,ho in G:
    eh=ELO[h]+(HOME if ho else 0); ea=ELO[a]
    lh,la=mm.elo_to_lambdas(eh,ea)            # v3.6 defaults
    style="open" if abs(eh-ea)>=300 else "balanced"
    P=mm.score_matrix(lh,la,opp_style=style)  # draw_boost default 0.06
    ph,pd,pa,_,_=mm.summarise(P)
    r=res(hg,ag); dirhit+=(max(range(3),key=lambda k:[ph,pd,pa][k])==r)
    rsum+=rps((ph,pd,pa),r); dps+=pd
    blow+=sum(p for (i,j),p in P.items() if abs(i-j)>=3)

RPS=rsum/n; DRAW=dps/n*100
print(f"n={n}  dir={dirhit}/{n}  RPS={RPS:.4f}  modelDraw%={DRAW:.1f}  blowExp={blow:.1f}")
LOCK=dict(dir=33, rps=0.1537, draw=25.7, blow=13.3)
assert dirhit==LOCK["dir"],            f"dir {dirhit} != {LOCK['dir']}"
assert abs(RPS-LOCK["rps"])<0.0008,    f"RPS {RPS:.4f} drifted from {LOCK['rps']}"
assert abs(DRAW-LOCK["draw"])<0.6,     f"draw% {DRAW:.1f} drifted from {LOCK['draw']}"
assert abs(blow-LOCK["blow"])<0.6,     f"blowExp {blow:.1f} drifted from {LOCK['blow']}"
print("ALL v3.6 REGRESSION CHECKS PASSED")
