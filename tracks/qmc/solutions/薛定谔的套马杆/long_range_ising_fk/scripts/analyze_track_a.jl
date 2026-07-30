using Statistics, LinearAlgebra, Printf

root = length(ARGS)>0 ? ARGS[1] : joinpath(@__DIR__,"..","results","track_a_20260727")
out = joinpath(root,"analysis"); mkpath(out)

function readsummary(path)
    ls=readlines(path); h=split(ls[1],','); v=split(ls[2],',')
    Dict(h[i] => parse(Float64,v[i]) for i in eachindex(h))
end
rows=Dict{String,Float64}[]
for d in readdir(joinpath(root,"cells"); join=true)
    p=joinpath(d,"summary.csv"); isfile(p) && push!(rows,readsummary(p))
end
length(rows)==96 || error("expected 96 cells, found $(length(rows))")

key(r)=(r["sigma"],Int(r["L"]),r["beta"])
groups=Dict{Tuple{Float64,Int,Float64},Vector{Dict{String,Float64}}}()
for r in rows; push!(get!(groups,key(r),Dict{String,Float64}[]),r); end

open(joinpath(out,"aggregated.csv"),"w") do io
    println(io,"sigma,L,beta,nseeds,Rp,Rp_seed_se,Qm,Qm_seed_se,chi,chi_seed_se,tau_m2_max")
    for (k,rs) in sort(collect(groups); by=first)
        vals(name)=[r[name] for r in rs]
        se(v)=length(v)>1 ? std(v)/sqrt(length(v)) : NaN
        @printf(io,"%.3f,%d,%.6f,%d,%.10g,%.10g,%.10g,%.10g,%.10g,%.10g,%.10g\n",
          k[1],k[2],k[3],length(rs),mean(vals("Rp")),se(vals("Rp")),
          mean(vals("Qm")),se(vals("Qm")),mean(vals("chi")),se(vals("chi")),
          maximum(vals("tau_m2")))
    end
end

bcs=Dict(1.75=>0.329136,1.875=>0.336985,2.0=>0.344439,2.5=>0.369446)
central=Dict{Tuple{Float64,Int},Dict{String,Float64}}()
for (k,rs) in groups
    abs(k[3]-bcs[k[1]])<1e-9 || continue
    central[(k[1],k[2])]=Dict(n=>mean(r[n] for r in rs) for n in ("Rp","Qm","chi"))
end

function linfit(X,y)
    b=X\y; resid=y-X*b; rss=sum(abs2,resid)
    b,rss
end
function powerfit(L,y)
    best=nothing
    for w in 0.05:0.01:2.0
        X=hcat(ones(length(L)),L.^(-w)); b,rss=linfit(X,y)
        (best===nothing || rss<best.rss) && (best=(Oinf=b[1],a=b[2],shape=w,rss=rss))
    end
    best
end
function logfit(L,y)
    best=nothing
    for l0 in exp.(range(log(.1),log(63.0),length=500))
        X=hcat(ones(length(L)),1 ./ log.(L./l0)); b,rss=linfit(X,y)
        (best===nothing || rss<best.rss) && (best=(Oinf=b[1],a=b[2],shape=l0,rss=rss))
    end
    best
end
scores(rss,n,k) = (aicc = n>k+1 ? n*log(max(rss,eps())/n)+2k+2k*(k+1)/(n-k-1) : NaN,
                   bic = n*log(max(rss,eps())/n)+k*log(n))

open(joinpath(out,"finite_size_fits.csv"),"w") do io
    println(io,"sigma,observable,Lmin,model,Oinf,amplitude,shape,rss,AICc,BIC,status")
    for s in sort(collect(keys(bcs))), obs in ("Rp","Qm")
        for Lmin in (64,128)
            L=Float64[l for l in (64,128,256,512) if l>=Lmin]
            y=[central[(s,Int(l))][obs] for l in L]
            for (name,f) in (("power",powerfit),("log",logfit))
                z=f(L,y); sc=scores(z.rss,length(L),3)
                status=length(L)>3 ? "rankable" : "underdetermined"
                @printf(io,"%.3f,%s,%d,%s,%.10g,%.10g,%.10g,%.10g,%.10g,%.10g,%s\n",
                  s,obs,Lmin,name,z.Oinf,z.a,z.shape,z.rss,sc.aicc,sc.bic,status)
            end
        end
    end
end

open(joinpath(out,"eta_fits.csv"),"w") do io
    println(io,"sigma,Lmin,eta,amplitude,rss")
    for s in sort(collect(keys(bcs))), Lmin in (64,128)
        L=Float64[l for l in (64,128,256,512) if l>=Lmin]
        y=log.([central[(s,Int(l))]["chi"] for l in L])
        b,rss=linfit(hcat(ones(length(L)),log.(L)),y)
        @printf(io,"%.3f,%d,%.10g,%.10g,%.10g\n",s,Lmin,2-b[2],exp(b[1]),rss)
    end
end

open(joinpath(out,"crossings.csv"),"w") do io
    println(io,"sigma,observable,L,2L,beta_cross,status")
    for s in sort(collect(keys(bcs))), obs in ("Rp","Qm"), (L1,L2) in ((64,128),(128,256),(256,512))
        betas=sort(unique(k[3] for k in keys(groups) if k[1]==s && k[2]==L1))
        d=Float64[]
        for b in betas
            push!(d,mean(r[obs] for r in groups[(s,L1,b)])-mean(r[obs] for r in groups[(s,L2,b)]))
        end
        X=hcat(ones(3),betas); coef=X\d; bc=-coef[1]/coef[2]
        ok=minimum(betas)<=bc<=maximum(betas)
        @printf(io,"%.3f,%s,%d,%d,%.10g,%s\n",s,obs,L1,L2,bc,ok ? "interpolated" : "unresolved")
    end
end

println("analysis complete: $(joinpath(root,"analysis"))")
