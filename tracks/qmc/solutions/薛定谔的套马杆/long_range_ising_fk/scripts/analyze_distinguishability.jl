#!/usr/bin/env julia

using Statistics, LinearAlgebra, Random, Printf

const BCS = Dict(1.75=>0.329136, 1.875=>0.336985,
                 2.0=>0.344439, 2.5=>0.369446)
const CANDIDATES = [3072,4096,6144,8192,12288,16384,32768,65536]

parsefloat(x) = parse(Float64, x)

function csv_rows(path)
    lines = readlines(path)
    isempty(lines) && return Dict{String,String}[]
    header = split(lines[1], ',')
    [Dict(header[i]=>v for (i,v) in enumerate(split(line, ',')))
     for line in lines[2:end] if !isempty(strip(line))]
end

function read_cells(root)
    rows = Dict{String,String}[]
    cells = joinpath(root, "cells")
    isdir(cells) || return rows
    for (dir, _, files) in walkdir(cells)
        "summary.csv" in files || continue
        for row in csv_rows(joinpath(dir, "summary.csv"))
            get(row, "role", "critical") == "critical" || continue
            sigma = parsefloat(row["sigma"])
            abs(parsefloat(row["beta"])-BCS[sigma]) <= 1e-9 || continue
            push!(rows, row)
        end
    end
    rows
end

function aggregate(rows)
    groups = Dict{Tuple{Float64,Int,Float64},Vector{Dict{String,String}}}()
    for row in rows
        key=(parsefloat(row["sigma"]),parse(Int,row["L"]),parsefloat(row["beta"]))
        push!(get!(groups,key,Dict{String,String}[]),row)
    end
    result=NamedTuple[]
    for ((sigma,L,beta), rs) in groups, obs in ("Rp","Qm")
        vals=parsefloat.([r[obs] for r in rs])
        se=length(vals)>1 ? std(vals)/sqrt(length(vals)) : NaN
        push!(result,(;sigma,L,beta,observable=obs,value=mean(vals),
                      se,nseeds=length(vals)))
    end
    sort(result,by=x->(x.sigma,x.observable,x.L))
end

feature(model,L,q) = model=="power" ? L.^(-q) : 1 ./ log.(L./q)
predict(model,L,p) = p[1] .+ p[2].*feature(model,L,p[3])

function grid_values(model,L)
    lo,hi = model=="power" ? (0.02,5.0) : (1e-4,minimum(L)*0.999)
    exp.(range(log(lo),log(hi),length=600))
end

function fit_core(model,L,y,se)
    w=1 ./ se
    best=(Inf,zeros(3))
    for q in grid_values(model,L)
        X=hcat(ones(length(L)),feature(model,L,q))
        coef=(X.*w) \ (y.*w)
        chi2=sum(abs2,(y-X*coef)./se)
        chi2 < best[1] && (best=(chi2,[coef[1],coef[2],q]))
    end
    p=best[2]
    base=predict(model,L,p)
    J=zeros(length(L),3)
    for j in 1:3
        step=1e-5*max(1,abs(p[j]))
        pp=copy(p); pp[j]+=step
        J[:,j]=(predict(model,L,pp)-base)./step
    end
    cov=pinv((J./se)'*(J./se))
    p,cov,best[1]
end

function fit_stats(model,L,y,se)
    p,cov,chi2=fit_core(model,L,y,se)
    n=length(L); k=3
    aic=chi2+2k
    aicc=n>k+1 ? aic+2k*(k+1)/(n-k-1) : Inf
    bic=chi2+k*log(n)
    loo=0.0; failures=0
    for i in eachindex(L)
        keep=[j for j in eachindex(L) if j!=i]
        try
            pp,_,_=fit_core(model,L[keep],y[keep],se[keep])
            loo+=((y[i]-predict(model,[L[i]],pp)[1])/se[i])^2
        catch
            failures+=1; loo=Inf
        end
    end
    (;p,cov,chi2,aicc,bic,loo,failures)
end

function predvar(model,x,p,cov)
    g=zeros(3); base=predict(model,[x],p)[1]
    for j in 1:3
        step=1e-5*max(1,abs(p[j]))
        pp=copy(p); pp[j]+=step
        g[j]=(predict(model,[x],pp)[1]-base)/step
    end
    max(0.0,dot(g,cov*g))
end

fmt(x) = x isa AbstractFloat ? @sprintf("%.12g",x) : string(x)
function write_table(path, rows)
    isempty(rows) && return
    names=collect(keys(rows[1]))
    open(path,"w") do io
        println(io,join(string.(names),","))
        for row in rows
            println(io,join((fmt(getproperty(row,n)) for n in names),","))
        end
    end
end

function main(args=ARGS)
    here=@__DIR__
    base=length(args)>=1 ? args[1] : joinpath(here,"..","results","track_a_20260727")
    large=length(args)>=2 ? args[2] : joinpath(here,"..","results","track_a_large_20260728")
    outdir=length(args)>=3 ? args[3] : joinpath(here,"..","results","track_a_extension_analysis")
    nboot=parse(Int,get(ENV,"TRACK_A_BOOTSTRAP","1000"))
    rng=MersenneTwister(860029)
    agg=aggregate(vcat(read_cells(base),read_cells(large)))
    mkpath(outdir)
    write_table(joinpath(outdir,"combined_critical.csv"),agg)
    extensionfits=NamedTuple[]
    for sigma in (1.875,2.0), obs in ("Rp","Qm")
        all_data=sort([x for x in agg if x.sigma==sigma && x.observable==obs],by=x->x.L)
        positives=[x.se for x in all_data if isfinite(x.se) && x.se>0]
        floor=isempty(positives) ? 1e-4 : median(positives)/2
        for maxL in (512,2048)
            data=[x for x in all_data if x.L<=maxL]
            L=Float64[x.L for x in data]; y=[x.value for x in data]
            se=[isfinite(x.se) ? max(floor,x.se) : floor for x in data]
            for model in ("power","marginal")
                f=fit_stats(model,L,y,se)
                push!(extensionfits,(;sigma,observable=obs,Lmin=Int(L[1]),
                      Lmax=Int(L[end]),n=length(L),model,limit=f.p[1],
                      p1=f.p[2],p2=f.p[3],chi2=f.chi2))
            end
        end
    end
    write_table(joinpath(outdir,"extension_comparison_fits.csv"),extensionfits)
    fits=NamedTuple[]; forecasts=NamedTuple[]
    for sigma in sort(unique(x.sigma for x in agg)), obs in ("Rp","Qm")
        data=sort([x for x in agg if x.sigma==sigma && x.observable==obs],by=x->x.L)
        length(data)>=5 || continue
        positives=[x.se for x in data if isfinite(x.se) && x.se>0]
        floor=isempty(positives) ? 1e-4 : median(positives)/2
        for first in 1:length(data)-4
            d=data[first:end]
            L=Float64[x.L for x in d]; y=[x.value for x in d]
            se=[isfinite(x.se) ? max(floor,x.se) : floor for x in d]
            fitted=Dict{String,Any}()
            for model in ("power","marginal")
                try
                    f=fit_stats(model,L,y,se); fitted[model]=f
                    limits=Float64[]; bootfail=0
                    for _ in 1:nboot
                        try
                            p,_,_=fit_core(model,L,y.+randn(rng,length(y)).*se,se)
                            push!(limits,p[1])
                        catch
                            bootfail+=1
                        end
                    end
                    q16,q84=isempty(limits) ? (NaN,NaN) :
                        (quantile(limits,.16),quantile(limits,.84))
                    push!(fits,(;sigma,observable=obs,Lmin=Int(L[1]),Lmax=Int(L[end]),
                      n=length(L),model,limit=f.p[1],p1=f.p[2],p2=f.p[3],
                      chi2=f.chi2,AICc=f.aicc,BIC=f.bic,LOO_chi2=f.loo,
                      loo_failures=f.failures,limit_boot_p16=q16,
                      limit_boot_p84=q84,bootstrap_failures=bootfail))
                catch
                end
            end
            haskey(fitted,"power") && haskey(fitted,"marginal") || continue
            fp=fitted["power"]; fm=fitted["marginal"]
            futurese=median(se[max(1,end-2):end])
            first3=">65536"; maxz=0.0
            for x in CANDIDATES
                delta=abs(predict("power",[x],fp.p)[1]-predict("marginal",[x],fm.p)[1])
                var=predvar("power",x,fp.p,fp.cov)+predvar("marginal",x,fm.p,fm.cov)+futurese^2
                z=var>0 ? delta/sqrt(var) : Inf
                maxz=max(maxz,z)
                first3==">65536" && z>=3 && (first3=string(x))
            end
            push!(forecasts,(;sigma,observable=obs,Lmin=Int(L[1]),Lmax=Int(L[end]),
                  first_3sigma_L=first3,max_separation_z=maxz,assumed_future_se=futurese))
        end
    end
    write_table(joinpath(outdir,"model_fits.csv"),fits)
    write_table(joinpath(outdir,"distinguishable_size.csv"),forecasts)
    println("cells=$(length(read_cells(base))+length(read_cells(large))) aggregated=$(length(agg)) fits=$(length(fits)) forecasts=$(length(forecasts)) out=$outdir")
end

abspath(PROGRAM_FILE) == (@__FILE__) && main()
