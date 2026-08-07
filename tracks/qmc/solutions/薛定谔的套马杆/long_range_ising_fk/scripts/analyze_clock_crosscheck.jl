#!/usr/bin/env julia

using Statistics, Printf

function rows(path)
    lines=readlines(path); header=split(lines[1],',')
    [Dict(header[i]=>v for (i,v) in enumerate(split(line,',')))
     for line in lines[2:end] if !isempty(strip(line))]
end

function cell_data(root)
    out=NamedTuple[]
    isdir(joinpath(root,"cells")) || return out
    for (dir,_,files) in walkdir(joinpath(root,"cells"))
        all(x->x in files,("summary.csv","blocks.csv")) || continue
        s=only(rows(joinpath(dir,"summary.csv")))
        b=rows(joinpath(dir,"blocks.csv"))
        L=parse(Int,s["L"]); sigma=parse(Float64,s["sigma"])
        qblocks=[parse(Float64,x["m2"])^2/parse(Float64,x["m4"]) for x in b]
        chiblocks=[L^2*parse(Float64,x["m2"]) for x in b]
        push!(out,(;L,sigma,seed=parse(Int,s["seed"]),
          Qm=parse(Float64,s["Qm"]),chi=parse(Float64,s["chi"]),
          tau=parse(Float64,s["tau_m2"]),qblocks,chiblocks))
    end
    out
end

function fk_data(path)
    out=Dict{Tuple{Float64,Int},NamedTuple}()
    for r in rows(path)
        sigma=parse(Float64,r["sigma"]); L=parse(Int,r["L"])
        beta=parse(Float64,r["beta"])
        bc=Dict(1.875=>0.336985,2.0=>0.344439)
        haskey(bc,sigma) || continue
        abs(beta-bc[sigma])<1e-9 || continue
        out[(sigma,L)]=(;Qm=parse(Float64,r["Qm"]),
          Qm_se=parse(Float64,r["Qm_seed_se"]),chi=parse(Float64,r["chi"]),
          chi_se=parse(Float64,r["chi_seed_se"]))
    end
    out
end

function main(args=ARGS)
    length(args)>=2 || error("usage: julia analyze_clock_crosscheck.jl CLOCK_ROOT FK_AGGREGATED [OUT]")
    clock=cell_data(args[1]); fk=fk_data(args[2])
    outfile=length(args)>=3 ? args[3] : joinpath(args[1],"comparison.csv")
    groups=Dict{Tuple{Float64,Int},Vector{NamedTuple}}()
    for x in clock
        push!(get!(groups,(x.sigma,x.L),NamedTuple[]),x)
    end
    open(outfile,"w") do io
        println(io,"sigma,L,nseeds,clock_Qm,clock_Qm_se,fk_Qm,fk_Qm_se,Qm_z,clock_chi,clock_chi_se,fk_chi,fk_chi_se,chi_z,tau_max")
        for key in sort(collect(keys(groups)))
            haskey(fk,key) || continue
            g=groups[key]; f=fk[key]
            qb=reduce(vcat,[x.qblocks for x in g])
            cb=reduce(vcat,[x.chiblocks for x in g])
            q=mean(x.Qm for x in g); qse=std(qb)/sqrt(length(qb))
            c=mean(x.chi for x in g); cse=std(cb)/sqrt(length(cb))
            qz=(q-f.Qm)/hypot(qse,f.Qm_se)
            cz=(c-f.chi)/hypot(cse,f.chi_se)
            println(io,join((key[1],key[2],length(g),q,qse,f.Qm,f.Qm_se,qz,
                             c,cse,f.chi,f.chi_se,cz,maximum(x.tau for x in g)),","))
        end
    end
    println("wrote $outfile")
end

abspath(PROGRAM_FILE) == (@__FILE__) && main()
