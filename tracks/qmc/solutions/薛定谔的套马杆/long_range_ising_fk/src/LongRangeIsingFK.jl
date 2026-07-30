module LongRangeIsingFK

using Random, Statistics, Printf, Dates, LinearAlgebra

export Geometry, WindingUF, add_edge!, wrapping, direct_sweep!, fast_sweep!,
       run_chain, minimum_delta, coupling_sum

minimum_delta(d::Int, L::Int) = mod(d + fld(L,2), L) - fld(L,2)

struct Geometry
    L::Int
    dx::Vector{Int}
    dy::Vector{Int}
    weight::Vector{Float64}
    cdf::Vector{Float64}
end

function Geometry(L::Int, sigma::Real)
    dx=Int[]; dy=Int[]; raw=Float64[]
    for y in 0:L-1, x in 0:L-1
        x==0 && y==0 && continue
        a=minimum_delta(x,L); b=minimum_delta(y,L)
        push!(dx,a); push!(dy,b); push!(raw,(a*a+b*b)^(-(2+sigma)/2))
    end
    w = 4 .* raw ./ sum(raw)
    Geometry(L,dx,dy,w,cumsum(w)./4)
end
coupling_sum(g::Geometry)=sum(g.weight)
site(x,y,L)=mod(x,L)+L*mod(y,L)+1
coords(i,L)=((i-1)%L,(i-1)÷L)

mutable struct WindingUF
    parent::Vector{Int}; size::Vector{Int}
    wx::Vector{Int}; wy::Vector{Int}
    wrapx::Vector{Bool}; wrapy::Vector{Bool}
end
WindingUF(n::Int)=WindingUF(collect(1:n),ones(Int,n),zeros(Int,n),zeros(Int,n),falses(n),falses(n))

function rootpot!(u::WindingUF, a::Int)
    p=u.parent[a]
    p==a && return (a,0,0)
    r,x,y=rootpot!(u,p)
    ox=u.wx[a]; oy=u.wy[a]
    u.parent[a]=r; u.wx[a]=ox+x; u.wy[a]=oy+y
    (r,u.wx[a],u.wy[a])
end

function add_edge!(u::WindingUF, a::Int, b::Int, dx::Int, dy::Int, L::Int)
    ra,ax,ay=rootpot!(u,a); rb,bx,by=rootpot!(u,b)
    vx=dx+ax-bx; vy=dy+ay-by # X_rb - X_ra
    if ra==rb
        u.wrapx[ra] |= vx != 0
        u.wrapy[ra] |= vy != 0
    elseif u.size[ra] >= u.size[rb]
        u.parent[rb]=ra; u.wx[rb]=vx; u.wy[rb]=vy
        u.size[ra]+=u.size[rb]
        u.wrapx[ra] |= u.wrapx[rb]; u.wrapy[ra] |= u.wrapy[rb]
    else
        u.parent[ra]=rb; u.wx[ra]=-vx; u.wy[ra]=-vy
        u.size[rb]+=u.size[ra]
        u.wrapx[rb] |= u.wrapx[ra]; u.wrapy[rb] |= u.wrapy[ra]
    end
end

function wrapping(u::WindingUF)
    anyx=false; anyy=false; both=false
    for i in eachindex(u.parent)
        u.parent[i]==i || continue
        anyx |= u.wrapx[i]; anyy |= u.wrapy[i]
        both |= u.wrapx[i] && u.wrapy[i]
    end
    (!anyx && !anyy, both, anyx, anyy)
end

function flip_clusters!(spins,u,rng)
    flips=Dict{Int,Bool}()
    for i in eachindex(spins)
        r,_,_=rootpot!(u,i)
        f=get!(flips,r,rand(rng,Bool))
        f && (spins[i] = -spins[i])
    end
    maximum(u.size[i] for i in eachindex(u.parent) if u.parent[i]==i)
end

function direct_sweep!(spins,g,beta,rng)
    N=length(spins); L=g.L; u=WindingUF(N)
    for a in 1:N-1
        xa,ya=coords(a,L)
        for b in a+1:N
            xb,yb=coords(b,L); dx=minimum_delta(xb-xa,L); dy=minimum_delta(yb-ya,L)
            k=findfirst(i->g.dx[i]==dx && g.dy[i]==dy, eachindex(g.dx))
            spins[a]==spins[b] && rand(rng)<-expm1(-2beta*g.weight[k]) && add_edge!(u,a,b,dx,dy,L)
        end
    end
    wr=wrapping(u); c1=flip_clusters!(spins,u,rng)
    wr,c1
end

function randpoisson(rng,lambda)
    total=0; chunks=max(1,ceil(Int,lambda/20)); lam=lambda/chunks
    for _ in 1:chunks
        limit=exp(-lam); p=1.0; k=0
        while true
            k+=1; p*=rand(rng)
            p<=limit && break
        end
        total += k-1
    end
    total
end

function fast_sweep!(spins,g,beta,rng)
    N=length(spins); L=g.L; u=WindingUF(N)
    for _ in 1:randpoisson(rng,4beta*N)
        a=rand(rng,1:N); k=searchsortedfirst(g.cdf,rand(rng))
        x,y=coords(a,L); b=site(x+g.dx[k],y+g.dy[k],L)
        spins[a]==spins[b] && add_edge!(u,a,b,g.dx[k],g.dy[k],L)
    end
    wr=wrapping(u); c1=flip_clusters!(spins,u,rng)
    wr,c1
end

function run_chain(;L=8,sigma=1.875,beta=0.336985,seed=1,therm=100,meas=500,algorithm=:fast,return_blocks=false)
    rng=MersenneTwister(seed); g=Geometry(L,sigma); spins=rand(rng,(-1,1),L^2)
    sweep! = algorithm==:fast ? fast_sweep! : direct_sweep!
    for _ in 1:therm; sweep!(spins,g,beta,rng); end
    mabs=Float64[]; m2=Float64[]; m4=Float64[]; r0=Float64[]; r2=Float64[]; c1=Float64[]
    t=time()
    for _ in 1:meas
        wr,c=sweep!(spins,g,beta,rng); m=sum(spins)/length(spins)
        push!(mabs,abs(m)); push!(m2,m^2); push!(m4,m^4)
        push!(r0,wr[1]); push!(r2,wr[2]); push!(c1,c)
    end
    q=mean(m2)^2/mean(m4); rp=mean(r2)-2mean(r0); chi=L^2*mean(m2)
    nb=min(20,max(2,meas÷50)); bs=meas÷nb
    block(v)=[mean(@view v[(i-1)*bs+1:i*bs]) for i in 1:nb]
    stderr(v)=std(block(v))/sqrt(nb)
    function tauint(v)
        z=v.-mean(v); den=sum(abs2,z); den==0 && return 0.5
        tau=0.5
        for lag in 1:min(100,meas÷10)
            rho=dot(@view(z[1:end-lag]),@view(z[1+lag:end]))/den
            rho<=0 && break
            tau+=rho
        end
        tau
    end
    summary=(;L,sigma,beta,seed,therm,meas,mean_abs_m=mean(mabs),mean_m2=mean(m2),
      mean_m4=mean(m4),Qm=q,chi,R0=mean(r0),R2=mean(r2),Rp=rp,
      mean_C1=mean(c1),se_m2=stderr(m2),se_Rp=stderr(r2.-2r0),
      tau_m2=tauint(m2),blocks=nb,runtime_s=time()-t,sumJ=coupling_sum(g))
    return_blocks ? (summary=summary, block_m2=block(m2), block_rp=block(r2.-2r0),
                     block_c1=block(c1)) : summary
end

end
