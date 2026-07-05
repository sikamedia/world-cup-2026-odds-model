#!/usr/bin/env python3
"""Probe the v3.4 candidate: steeper Elo->goal-diff slope (gd_per_100).
Self-contained. Confirms robustness (extended sweep, out-of-sample 4, joint with
avg_goals) before recommending. Educational/analytical use only — not betting advice."""
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
 "England":2024,"Croatia":1900,"Ghana":1750,"Panama":1640}
HOME=85
G=[("Mexico","South Africa",2,0,1,0),("Korea","Czechia",2,1,0,0),
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
 ("France","Iraq",3,0,0,1),("Norway","Senegal",3,2,0,1),
 ("Argentina","Austria",2,0,0,1),("Algeria","Jordan",2,1,0,1)]

def pois(k,l): return math.exp(-l)*l**k/math.factorial(k)
def negbin(k,mu,r):
    p=r/(r+mu); return math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1))*p**r*(1-p)**k
def dc(i,j,lh,la,rho):
    if i==0 and j==0:return 1-lh*la*rho
    if i==0 and j==1:return 1+lh*rho
    if i==1 and j==0:return 1+la*rho
    if i==1 and j==1:return 1-rho
    return 1.0
def smatrix(lh,la,rho=-0.05,style="balanced",disp=5.0,db=0.06,n=11):
    fav=lh>=la
    def m(k,l,f): return negbin(k,l,disp) if (style=="open" and f) else pois(k,l)
    P={};t=0.0
    for i in range(n):
        for j in range(n):
            p=m(i,lh,fav)*m(j,la,not fav)*dc(i,j,lh,la,rho); P[(i,j)]=p; t+=p
    P={k:v/t for k,v in P.items()}
    if db>0:
        d=sum(p for (i,j),p in P.items() if i==j)
        if 0<d<1:
            td=min(0.97,d+db); fd,fo=td/d,(1-td)/(1-d)
            P={(i,j):p*(fd if i==j else fo) for (i,j),p in P.items()}
    return P
def summ(P):
    h=d=a=ov=0.0
    for (i,j),p in P.items():
        if i>j:h+=p
        elif i==j:d+=p
        else:a+=p
        if i+j>=3:ov+=p
    return h,d,a,ov
def res(hg,ag): return 0 if hg>ag else (1 if hg==ag else 2)
def rps(pr,r):
    oc=[1 if r==k else 0 for k in range(3)];cp=co=s=0.0
    for k in range(2):cp+=pr[k];co+=oc[k];s+=(cp-co)**2
    return s/2
def tip(h,d,a,gate): return 1 if (d>=0.26 and max(h,a)<gate) else (0 if h>a else 2)

def predict(h_,a_,ho,gd,ag_g,db,auto,delo,gate):
    eh=ELO[h_]+(HOME if ho else 0);ea=ELO[a_]
    diff=eh-ea;g=diff/100.0*gd;base=ag_g/2.0
    lh=max(0.15,base+g/2);la=max(0.15,base-g/2)
    style="open" if (auto and abs(eh-ea)>=delo) else "balanced"
    P=smatrix(lh,la,style=style,db=db);h,d,a,ov=summ(P);return h,d,a,ov,P

def run(games,gd=0.45,ag_g=2.8,db=0.06,auto=True,delo=300,gate=0.42):
    n=len(games);arg=rule=0;r_rps=ll=dps=brou=0.0;blowA=0;blowE=0.0;ouA=0;dA=0
    for h_,a_,hg,ag,ho,new in games:
        h,d,a,ov,P=predict(h_,a_,ho,gd,ag_g,db,auto,delo,gate);r=res(hg,ag)
        arg+=((0 if h>a else 2)==r);rule+=(tip(h,d,a,gate)==r)
        r_rps+=rps((h,d,a),r);ll+=math.log(max(P[(hg,ag)],1e-12));dps+=d
        if r==1:dA+=1
        if abs(hg-ag)>=3:blowA+=1
        blowE+=sum(p for (i,j),p in P.items() if abs(i-j)>=3)
        ov_=1 if hg+ag>=3 else 0;ouA+=ov_;brou+=(ov-ov_)**2
    return dict(n=n,arg=arg,rule=rule,rps=r_rps/n,ll=ll,drawM=dps/n,drawA=dA,
                blowA=blowA,blowE=blowE,brier=brou/n,ouA=ouA)

allg=G;new4=[g for g in G if g[5]==1];old40=[g for g in G if g[5]==0]

print("="*78)
print("EXTENDED gd_per_100 sweep  (does it keep improving or turn over?)")
print("  in-sample = 40 tuned games | out-of-sample = 4 new Jun-22 games")
print("="*78)
print(f"{'gd/100':>7}{'RPS44':>9}{'logL44':>9}{'WDLarg':>9}{'drawM%':>8}{'blowE':>7}"
      f"{'RPS_in40':>10}{'RPS_new4':>10}")
for gd in [0.40,0.45,0.50,0.55,0.60,0.65,0.70]:
    m=run(allg,gd=gd);mo=run(old40,gd=gd);mn=run(new4,gd=gd)
    print(f"{gd:>7.2f}{m['rps']:>9.4f}{m['ll']:>9.2f}{str(m['arg'])+'/44':>9}"
          f"{m['drawM']*100:>7.1f}%{m['blowE']:>7.1f}{mo['rps']:>10.4f}{mn['rps']:>10.4f}")
print(f"\nactual: draws 13/44=29.5%  blowouts(net>=3)=12  over2.5=24/44=55%")

print("\n"+"="*78)
print("JOINT gd_per_100 x avg_goals  (cell = RPS44 / O-U-Brier44)")
print("="*78)
print(f"{'':>9}"+"".join(f"{'ag='+str(a):>15}" for a in [2.7,2.8,2.9,3.0]))
for gd in [0.45,0.50,0.55,0.60]:
    cells=[f"{run(allg,gd=gd,ag_g=a)['rps']:.4f}/{run(allg,gd=gd,ag_g=a)['brier']:.3f}"
           for a in [2.7,2.8,2.9,3.0]]
    print(f"gd={gd:<6}"+"".join(f"{c:>15}" for c in cells))

print("\n"+"="*78)
print("HEAD-TO-HEAD: v3.3 (current) vs v3.4 candidate (gd .55, ag 2.9)")
print("="*78)
for label,(gd,ag_g) in [("v3.3  gd=.45 ag=2.8",(0.45,2.8)),
                        ("v3.4  gd=.55 ag=2.9",(0.55,2.9))]:
    m=run(allg,gd=gd,ag_g=ag_g);mo=run(old40,gd=gd,ag_g=ag_g);mn=run(new4,gd=gd,ag_g=ag_g)
    print(f"\n{label}")
    print(f"  FULL44: WDLarg {m['arg']}/44={m['arg']/44*100:.0f}%  Tipset {m['rule']}/44={m['rule']/44*100:.0f}%"
          f"  RPS {m['rps']:.4f}  logL {m['ll']:.1f}  OUbrier {m['brier']:.4f}")
    print(f"  IN40  : RPS {mo['rps']:.4f}  logL {mo['ll']:.1f}   ||   NEW4: RPS {mn['rps']:.4f}  WDL {mn['arg']}/4")
    print(f"  blowout exp {m['blowE']:.1f} (actual 12) | draw model {m['drawM']*100:.1f}% (actual 29.5%)")
print("\nEducational/analytical use only — not betting advice.")
