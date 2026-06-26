import math
from math import lgamma,exp,log,factorial
ELO = {
 "Mexico":1890,"South Africa":1720,"Korea":1785,"Czechia":1800,"Canada":1870,"Bosnia":1775,"Qatar":1640,"Switzerland":1891,
 "Brazil":1991,"Morocco":1860,"Haiti":1480,"Scotland":1780,"USA":1860,"Paraguay":1730,"Australia":1720,"Turkiye":1850,
 "Germany":1960,"Curacao":1500,"Cote dIvoire":1820,"Ecuador":1850,"Netherlands":1970,"Japan":1840,"Sweden":1810,"Tunisia":1720,
 "Belgium":1930,"Egypt":1628,"Iran":1810,"New Zealand":1500,"Spain":2157,"Cabo Verde":1620,"Saudi Arabia":1660,"Uruguay":1920,
 "France":2063,"Senegal":1880,"Iraq":1620,"Norway":1880,"Argentina":2115,"Algeria":1800,"Austria":1820,"Jordan":1640,
 "Portugal":1989,"DR Congo":1700,"Uzbekistan":1690,"Colombia":1982,"England":2024,"Croatia":1900,"Ghana":1750,"Panama":1640,
}
def pois(k,l): return exp(-l)*l**k/factorial(k)
def negbin(k,mu,r):
    p=r/(r+mu); return exp(lgamma(k+r)-lgamma(r)-lgamma(k+1))*p**r*(1-p)**k
# v3.4 params
GD=0.55; AVG=2.85; DB=0.07; R=5
def lams(eh,ea,home=0):
    d=(eh+home)-ea; gd=d/100*GD; b=AVG/2
    return max(.15,b+gd/2),max(.15,b-gd/2),d
def matrix(eh,ea,home=0,N=11):
    lh,la,d=lams(eh,ea,home)
    favopen = abs(d)>=300  # opp-style auto
    P={}
    for i in range(N):
        for j in range(N):
            pi = (negbin(i,lh,R) if (favopen and lh>=la) else pois(i,lh))
            pj = (negbin(j,la,R) if (favopen and la>lh) else pois(j,la))
            P[(i,j)]=pi*pj
    s=sum(P.values()); P={k:v/s for k,v in P.items()}
    dd=sum(p for (i,j),p in P.items() if i==j)
    if 0<dd<1:
        td=min(.97,dd+DB); fd=td/dd; fo=(1-td)/(1-dd)
        P={(i,j):p*(fd if i==j else fo) for (i,j),p in P.items()}
    return P
def wdl(P):
    h=sum(p for (i,j),p in P.items() if i>j); dr=sum(p for (i,j),p in P.items() if i==j)
    return h,dr,1-h-dr
G=[ # 40 prior + 8 new ; (home,away,hg,ag,hosthome)
 ("Mexico","South Africa",2,0,1),("Korea","Czechia",2,1,0),("Mexico","Korea",1,0,1),("South Africa","Czechia",1,1,0),
 ("Qatar","Switzerland",1,1,0),("Canada","Bosnia",1,1,1),("Switzerland","Bosnia",4,1,0),("Canada","Qatar",6,0,1),
 ("Brazil","Morocco",1,1,0),("Scotland","Haiti",1,0,0),("Morocco","Scotland",1,0,0),("Brazil","Haiti",3,0,0),
 ("USA","Paraguay",4,1,1),("Australia","Turkiye",2,0,0),("USA","Australia",2,0,1),("Paraguay","Turkiye",1,0,0),
 ("Germany","Curacao",7,1,0),("Cote dIvoire","Ecuador",1,0,0),("Germany","Cote dIvoire",2,1,0),("Ecuador","Curacao",0,0,0),
 ("Netherlands","Japan",2,2,0),("Sweden","Tunisia",5,1,0),("Netherlands","Sweden",5,1,0),("Japan","Tunisia",4,0,0),
 ("Belgium","Egypt",1,1,0),("Iran","New Zealand",2,2,0),("Belgium","Iran",0,0,0),("New Zealand","Egypt",1,3,0),
 ("Spain","Cabo Verde",0,0,0),("Saudi Arabia","Uruguay",1,1,0),("Spain","Saudi Arabia",4,0,0),("Uruguay","Cabo Verde",2,2,0),
 ("France","Senegal",3,1,0),("Norway","Iraq",4,1,0),("Argentina","Algeria",3,0,0),("Austria","Jordan",3,1,0),
 ("Portugal","DR Congo",1,1,0),("Colombia","Uzbekistan",3,1,0),("England","Croatia",4,2,0),("Ghana","Panama",1,0,0),
 # --- 8 NEW (June 22-23) ---
 ("Argentina","Austria",2,0,0),("France","Iraq",3,0,0),("Norway","Senegal",3,2,0),("Algeria","Jordan",2,1,0),
 ("Portugal","Uzbekistan",5,0,0),("England","Ghana",0,0,0),("Panama","Croatia",0,1,0),("Colombia","DR Congo",1,0,0),
 ("Mexico","Czechia",3,0,1),("South Africa","Korea",1,0,0),
]
HOME=85
def res(hg,ag): return 0 if hg>ag else (1 if hg==ag else 2)
def pick(h,d,a): # v3.4 gate 0.42
    if d>=.26 and max(h,a)<.42: return 1
    return 0 if h>a else 2
n=len(G); corr=0; rps=0; lls=0; da=dp=0; ba=0; be=0.0
for h,a,hg,ag,ho in G:
    P=matrix(ELO[h],ELO[a],HOME if ho else 0)
    ph,pd,pa=wdl(P); r=res(hg,ag)
    corr+= (pick(ph,pd,pa)==r)
    pc=[ph,pd,pa]; oc=[1 if r==k else 0 for k in range(3)]
    cp=co=ss=0
    for k in range(2): cp+=pc[k]; co+=oc[k]; ss+=(cp-co)**2
    rps+=ss/2
    lls+=log(P[(hg,ag)])
    if r==1:da+=1
    if pick(ph,pd,pa)==1:dp+=1
    if abs(hg-ag)>=3:ba+=1
    be+=sum(p for (i,j),p in P.items() if abs(i-j)>=3)
print(f"=== v3.4 backtest, {n} games ===")
print(f"W/D/L accuracy: {corr}/{n} = {corr/n*100:.0f}%")
print(f"RPS (avg): {rps/n:.4f}")
print(f"avg scoreline logL: {lls/n:.3f}")
print(f"DRAWS actual {da} | picked {dp}")
print(f"BLOWOUTS (net>=3) actual {ba} | model expected {be:.1f}")
