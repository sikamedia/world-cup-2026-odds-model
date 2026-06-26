from math import lgamma,exp,log,factorial
# import only the data (ELO dict + G list) from the 50-game file
full=open("backtest_v34_50.py").read()
data=full.split("HOME=85")[0]          # ELO, defs, and G list literal (no run)
ns={'math':__import__('math'),'lgamma':lgamma,'exp':exp,'log':log,'factorial':factorial}
exec(data,ns); ELO=ns['ELO']; G=ns['G']
def pois(k,l): return exp(-l)*l**k/factorial(k)
def negbin(k,mu,r):
    p=r/(r+mu); return exp(lgamma(k+r)-lgamma(r)-lgamma(k+1))*p**r*(1-p)**k
def run(GD,AVG,DB,GATE,AUTO,R=5,HOME=85):
    def lams(eh,ea,home):
        d=(eh+home)-ea; gd=d/100*GD; b=AVG/2
        return max(.15,b+gd/2),max(.15,b-gd/2),d
    def mat(eh,ea,home):
        lh,la,d=lams(eh,ea,home); fav=(abs(d)>=300 and AUTO)
        P={}
        for i in range(11):
            for j in range(11):
                pi=negbin(i,lh,R) if(fav and lh>=la) else pois(i,lh)
                pj=negbin(j,la,R) if(fav and la>lh) else pois(j,la)
                P[(i,j)]=pi*pj
        s=sum(P.values()); P={k:v/s for k,v in P.items()}
        dd=sum(p for(i,j),p in P.items() if i==j)
        if DB>0 and 0<dd<1:
            td=min(.97,dd+DB); fd=td/dd; fo=(1-td)/(1-dd)
            P={(i,j):p*(fd if i==j else fo) for(i,j),p in P.items()}
        return P
    def wdl(P):
        h=sum(p for(i,j),p in P.items() if i>j); dr=sum(p for(i,j),p in P.items() if i==j)
        return h,dr,1-h-dr
    res=lambda hg,ag:0 if hg>ag else(1 if hg==ag else 2)
    def pick(h,d,a):
        return 1 if (d>=.26 and max(h,a)<GATE) else (0 if h>a else 2)
    n=len(G); c=0; rps=0; lls=0
    for h,a,hg,ag,ho in G:
        P=mat(ELO[h],ELO[a],HOME if ho else 0); ph,pd,pa=wdl(P); r=res(hg,ag)
        c+=(pick(ph,pd,pa)==r)
        pc=[ph,pd,pa]; oc=[1 if r==k else 0 for k in range(3)]; cp=co=ss=0
        for k in range(2): cp+=pc[k]; co+=oc[k]; ss+=(cp-co)**2
        rps+=ss/2; lls+=log(P[(hg,ag)])
    return c,n,rps/n,lls/n
print(f"同样 {len(G)} 场,两套参数对比:")
print(f"{'版本':<16}{'W/D/L':>12}{'RPS':>9}{'比分logL':>10}")
c,n,r,l=run(0.45,2.6,0.06,0.52,False); print(f"{'v3.2(旧)':<14}{c}/{n}={c/n*100:.0f}%{r:>9.4f}{l:>10.3f}")
c,n,r,l=run(0.55,2.85,0.07,0.42,True); print(f"{'v3.4(改进)':<13}{c}/{n}={c/n*100:.0f}%{r:>9.4f}{l:>10.3f}")
