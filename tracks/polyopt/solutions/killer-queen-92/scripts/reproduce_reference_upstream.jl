using Pkg

commit = ENV["SPECTRALGAP_COMMIT"]
environment = joinpath(@__DIR__,"..",".raw","spectralgap-reference-env")
Pkg.activate(environment)
Pkg.add(PackageSpec(url="https://github.com/wangjie212/SpectralGap",rev=commit))
@eval using SpectralGap

N = 5
g = 0.5
d = 2
H = SpectralGap.ncpoly([[3*[i;i+1] for i=1:N-1]; [[3i-2] for i=1:N]],[-ones(N-1);g*ones(N)])
basis = [SpectralGap.get_basis(N,d,label=i) for i in (1,2)]
gbasis = [SpectralGap.get_bulkbasis(N,d-1,label=i) for i in (1,2)]
blocks = [length.(basis);length.(gbasis)]

lower,upper = 0.0,1.0
while upper-lower > 0.005
    gamma = (lower+upper)/2
    flag = SpectralGap.certify_Ising_gap(N,H,gamma,d,QUIET=true)
    if flag==1
        lower=gamma
    else
        upper=gamma
    end
    println("reference progress: [$lower,$upper]")
    flush(stdout)
end
mosek_version = string(Pkg.dependencies()[Base.UUID("6405355b-0ac2-5fba-af84-adbd65488c0e")].version)
payload = "{\"endpoint\":$upper,\"lower\":$lower,\"actual_blocks\":$(blocks),\"mosek_version\":\"$mosek_version\"}"
println("REFERENCE_JSON:"*payload)
flush(stdout)
