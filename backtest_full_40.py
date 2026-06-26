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
def pois(k,l): return math.exp(-l)*l**k/math.factorial(k)
def lams(eh,ea,home=0):
    d=(eh+home)-ea; gd=d/100*0.45; b=1.3
    return max(.15,b+gd/2),max(.15,b-gd/2)
def matrix(eh,ea,home=0,N=11):
    lh,la=lams(eh,ea,home); P={}
    for i in range(N):
        for j in range(N): P[(i,j)]=pois(i,lh)*pois(j,la)
    return P
def wdl(P):
    h=d=a=0
    for (i,j),p in P.items():
        h+= p if i>j else 0; d+= p if i==j else 0; a+= p if i<j else 0
    return h,d,a

G=[ # home, away, hg, ag, hosthome
 ("Mexico","South Africa",2,0,1),("Korea","Czechia",2,1,0),("Mexico","Korea",1,0,1),("South Africa","Czechia",1,1,0),
 ("Qatar","Switzerland",1,1,0),("Canada","Bosnia",1,1,1),("Switzerland","Bosnia",4,1,0),("Canada","Qatar",6,0,1),
 ("Brazil","Morocco",1,1,0),("Scotland","Haiti",1,0,0),("Morocco","Scotland",1,0,0),("Brazil","Haiti",3,0,0),
 ("USA","Paraguay",4,1,1),("Australia","Turkiye",2,0,0),("USA","Australia",2,0,1),("Paraguay","Turkiye",1,0,0),
 ("Germany","Curacao",7,1,0),("Cote dIvoire","Ecuador",1,0,0),("Germany","Cote dIvoire",2,1,0),("Ecuador","Curacao",0,0,0),
 ("Netherlands","Japan",2,2,0),("Sweden","Tunisia",5,1,0),("Netherlands","Sweden",5,1,0),("Japan","Tunisia",4,0,0),
 ("Belgium","Egypt",1,1,0),("Iran","New Zealand",2,2,0),("Belgium","Iran",0,0,0),("New Zealand","Egypt",1,3,0),
 ("Spain","Cabo Verde",0,0,0),("Saudi Arabia","Uruguay",1,1,0),("Spain","Saudi Arabia",4,0,0),("Uruguay","Cabo Verde",2,2,0),
 ("France","Senegal",3,1,0),("Norway","Iraq",4,1,0),
 ("Argentina","Algeria",3,0,0),("Austria","Jordan",3,1,0),
 ("Portugal","DR Congo",1,1,0),("Colombia","Uzbekistan",3,1,0),
 ("England","Croatia",4,2,0),("Ghana","Panama",1,0,0),
]
HOME=85
def res(hg,ag): return 0 if hg>ag else (1 if hg==ag else 2)  # 0=H,1=D,2=A
def pick(h,d,a):
    if d>=.26 and max(h,a)<.52: return 1
    return 0 if h>a else 2
n=len(G); wdl_argmax=wdl_rule=0; rps=0; ll_score=0
da=dp=0; blow_act=0; blow_exp=0.0
for h,a,hg,ag,ho in G:
    P=matrix(ELO[h],ELO[a],HOME if ho else 0)
    ph,pd,pa=wdl(P); r=res(hg,ag)
    # argmax (no draw)
    am=0 if ph>pa else 2  # argmax never draws in practice
    wdl_argmax += (am==r)
    wdl_rule += (pick(ph,pd,pa)==r)
    # RPS (ranked prob score, lower=better) for ordered H,D,A
    pc=[ph,pd,pa]; oc=[1 if r==k else 0 for k in range(3)]
    cp=co=0; s=0
    for k in range(2):
        cp+=pc[k]; co+=oc[k]; s+=(cp-co)**2
    rps += s/2
    # scoreline log-likelihood
    ll_score += math.log(P[(hg,ag)] / sum(P.values()))
    if r==1: da+=1
    if pick(ph,pd,pa)==1: dp+=1
    if abs(hg-ag)>=3: blow_act+=1
    blow_exp += sum(p for (i,j),p in P.items() if abs(i-j)>=3)/sum(P.values())
print(f"games: {n}")
print(f"W/D/L accuracy  argmax(H/A only): {wdl_argmax}/{n} = {wdl_argmax/n*100:.0f}%")
print(f"W/D/L accuracy  with draw rule  : {wdl_rule}/{n} = {wdl_rule/n*100:.0f}%")
print(f"RPS (avg, lower=better): {rps/n:.3f}")
print(f"avg log-likelihood of actual scoreline: {ll_score/n:.3f}")
print(f"DRAWS  actual: {da}  | model picked: {dp}")
print(f"BLOWOUTS (net>=3)  actual: {blow_act}  | model EXPECTED (sum prob): {blow_exp:.1f}")

# --- diagnostic: is DRAW PROBABILITY itself under-estimated? ---
avg_draw=0; 
for h,a,hg,ag,ho in G:
    ph,pd,pa=wdl(matrix(ELO[h],ELO[a],HOME if ho else 0)); avg_draw+=pd
avg_draw/=n
print(f"\navg model draw prob: {avg_draw*100:.1f}%   actual draw rate: {da}/{n} = {da/n*100:.1f}%")

# --- test a DRAW-INFLATION fix: move mass into draw, re-score RPS ---
def inflate(ph,pd,pa,boost):
    pd2=pd+boost; s=ph+pa
    if s<=0: return ph,pd2,pa
    return ph*(1-boost/ (ph+pa))*1, pd2, pa*(1-boost/(ph+pa))
import itertools
print("\nDraw-inflation test (move X mass into draw):")
for boost in [0.0,0.04,0.07,0.10]:
    rps=0
    for h,a,hg,ag,ho in G:
        ph,pd,pa=wdl(matrix(ELO[h],ELO[a],HOME if ho else 0))
        pd2=pd+boost; sc=ph+pa; ph2=ph-boost*ph/sc; pa2=pa-boost*pa/sc
        r=res(hg,ag); pc=[ph2,pd2,pa2]; oc=[1 if r==k else 0 for k in range(3)]
        cp=co=0; sm=0
        for k in range(2): cp+=pc[k]; co+=oc[k]; sm+=(cp-co)**2
        rps+=sm/2
    print(f"  draw boost +{boost*100:.0f}%: RPS = {rps/n:.4f}")
