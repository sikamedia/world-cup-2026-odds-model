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
def lambdas(eh,ea,home=0):
    d=(eh+home)-ea; gd=d/100*0.45; b=1.3
    return max(.15,b+gd/2), max(.15,b-gd/2)
def wdl(eh,ea,home=0,N=11):
    lh,la=lambdas(eh,ea,home); h=dr=a=0
    for i in range(N):
        for j in range(N):
            p=pois(i,lh)*pois(j,la)
            if i>j:h+=p
            elif i==j:dr+=p
            else:a+=p
    return h,dr,a

# played games: (home, away, hg, ag, host_home?) host=USA/CAN/MEX at home
played = [
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
 ("Spain","Cabo Verde",0,0,0),("Saudi Arabia","Uruguay",1,1,0),
 ("France","Senegal",3,1,0),("Norway","Iraq",4,1,0),
 ("Argentina","Algeria",3,0,0),("Austria","Jordan",3,1,0),
 ("Portugal","DR Congo",1,1,0),("Colombia","Uzbekistan",3,1,0),
 ("England","Croatia",4,2,0),("Ghana","Panama",1,0,0),
]
HOME=85
def actual(hg,ag): return "H" if hg>ag else ("D" if hg==ag else "A")
def pick(h,dr,a):
    m=max(h,dr,a); return "H" if m==h else ("D" if m==dr else "A")

corr=draws_actual=draws_picked=0
fav_corr=0  # favorite (ignoring draw) right when not a draw
print(f"{'match':<34}{'modelW/D/L':>18}{'pick':>5}{'act':>4}{'ok':>4}")
for h,a,hg,ag,ho in played:
    H=HOME if ho else 0
    ph,pd,pa=wdl(ELO[h],ELO[a],H)
    pk=pick(ph,pd,pa); ac=actual(hg,ag)
    ok = pk==ac
    corr+=ok
    if ac=="D":draws_actual+=1
    if pk=="D":draws_picked+=1
    print(f"{h+' v '+a:<34}{f'{ph*100:.0f}/{pd*100:.0f}/{pa*100:.0f}':>18}{pk:>5}{f'{hg}-{ag}':>5}{'Y' if ok else '.':>3}")
n=len(played)
print(f"\nW/D/L accuracy: {corr}/{n} = {corr/n*100:.0f}%")
print(f"Actual draws: {draws_actual}/{n} ({draws_actual/n*100:.0f}%)   Model PICKED draw: {draws_picked} times")
print("=> if model rarely/never picks 'D', that's the gap to fix (draw-selection rule).")

print("\n\n===== 测试平局判定规则 =====")
# 规则:当 draw% >= 26% 且 没有一方是大热门(max(H,A) < 52%)→ 判平;否则取 H/A 较大者
def pick2(h,dr,a):
    if dr>=0.26 and max(h,a)<0.52: return "D"
    return "H" if h>a else "A"
c1=c2=0
for h,a,hg,ag,ho in played:
    H=85 if ho else 0
    ph,pd,pa=wdl(ELO[h],ELO[a],H); ac=actual(hg,ag)
    c1 += (pick(ph,pd,pa)==ac)
    c2 += (pick2(ph,pd,pa)==ac)
n=len(played)
print(f"原(取最大): {c1}/{n} = {c1/n*100:.0f}%   含平局规则: {c2}/{n} = {c2/n*100:.0f}%")

print("\n\n===== 13 场预测(MD3) =====")
# (home, away, home_bump, note)  bump = 主场+海拔(仅东道主/高原)
fixtures = [
 ("Argentina","Austria",0,"中立(AT&T顶棚) Argentina强"),
 ("France","Iraq",0,"中立 France碾压"),
 ("Norway","Senegal",0,"中立 实力接近→平局候选"),
 ("Jordan","Algeria",0,"中立 Algeria占优"),
 ("England","Ghana",0,"中立 England强"),
 ("Panama","Croatia",0,"中立 Croatia占优"),
 ("Colombia","DR Congo",0,"瓜达拉哈拉1566m中立 Colombia占优"),
 ("Switzerland","Canada",-85,"BC Place 加拿大主场(+85给客队Canada)"),
 ("Bosnia","Qatar",0,"中立 Bosnia略占优"),
 ("Morocco","Haiti",0,"亚特兰大顶棚关 海地已出局/脆弱→open"),
 ("Scotland","Brazil",0,"迈阿密高温 Brazil强"),
 ("Czechia","Mexico",-120,"阿兹特克2240m高原+墨西哥主场(+120给客队Mexico);墨已锁头名或轮换"),
 ("South Africa","Korea",0,"蒙特雷~540m 接近→平局候选"),
]
print(f"{'match':<26}{'W/D/L%':>16}{'pick(rule)':>11}")
for h,a,hb,note in fixtures:
    # hb<0 means away team gets the bump (home advantage to away side)
    if hb>=0:
        ph,pd,pa=wdl(ELO[h],ELO[a],hb)
    else:
        pa,pd,ph=wdl(ELO[a],ELO[h],-hb)  # swap: away is the 'home-advantaged'
    pk=pick2(ph,pd,pa)
    lab={"H":h,"D":"Draw","A":a}[pk]
    print(f"{h+' v '+a:<26}{f'{ph*100:.0f}/{pd*100:.0f}/{pa*100:.0f}':>16}{lab:>11}   {note}")
